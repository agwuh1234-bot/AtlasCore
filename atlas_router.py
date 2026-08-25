from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any

from atlas_store import AtlasStore, BudgetExceeded


@dataclass(frozen=True)
class RouteDecision:
    lane: str
    model: str
    use_web: bool
    reason: str


@dataclass
class BudgetReservation:
    id: str
    model: str
    estimated_input_tokens: int
    estimated_cost_usd: float
    use_web: bool


class ModelRouter:
    """Route routine work cheaply while keeping complex reasoning on the strongest model."""

    def __init__(self) -> None:
        self.fast_model = os.environ.get("ATLAS_MODEL_FAST", "gpt-5.6-luna")
        self.document_model = os.environ.get("ATLAS_MODEL_DOCUMENT", "gpt-5.6-terra")
        self.strong_model = os.environ.get("ATLAS_MODEL_STRONG", "gpt-5.6-sol")
        self.fallback_model = os.environ.get("ATLAS_MODEL_FALLBACK", "gpt-5.4-mini")

    def select(
        self,
        text: str,
        *,
        has_attachments: bool = False,
        claude_review: bool = False,
    ) -> RouteDecision:
        lowered = (text or "").lower()
        use_web = self._needs_fresh_information(lowered)
        strong = self._needs_strong_model(
            lowered,
            has_attachments=has_attachments,
            claude_review=claude_review,
        )
        if strong:
            return RouteDecision(
                lane="strong",
                model=self.strong_model,
                use_web=use_web,
                reason="code_or_complex_reasoning",
            )
        if has_attachments:
            return RouteDecision(
                lane="document",
                model=self.document_model,
                use_web=use_web,
                reason="attachment_analysis",
            )
        if use_web:
            return RouteDecision(
                lane="fresh",
                model=self.fast_model,
                use_web=True,
                reason="fresh_information",
            )
        return RouteDecision(
            lane="fast",
            model=self.fast_model,
            use_web=False,
            reason="routine_request",
        )

    @staticmethod
    def _needs_fresh_information(text: str) -> bool:
        terms = (
            "сегодня", "сейчас", "последн", "свеж", "новост", "актуальн",
            "текущ", "цена", "курс", "погода", "расписан", "кто сейчас",
            "latest", "today", "current", "recent", "news", "price",
            "weather", "schedule", "search the web", "найди в интернете",
            "проверь в интернете",
        )
        return any(term in text for term in terms)

    @staticmethod
    def _needs_strong_model(
        text: str,
        *,
        has_attachments: bool,
        claude_review: bool,
    ) -> bool:
        if claude_review:
            return True
        terms = (
            "код", "репозитор", "архитект", "рефактор", "отлад", "debug",
            "python", "javascript", "typescript", "sql", "api", "deploy",
            "railway", "github", "тест", "ошибк", "сложн",
            "сравни варианты", "план миграции", "security", "безопасност",
            "code", "architecture", "implement", "fix", "reason step",
        )
        # A file alone no longer forces the most expensive model. Files use the
        # document lane unless the user's request itself clearly needs Sol.
        return any(term in text for term in terms) or len(text) > 2500

    def public_config(self) -> dict[str, str]:
        return {
            "fast": self.fast_model,
            "document": self.document_model,
            "strong": self.strong_model,
            "fallback": self.fallback_model,
        }


class PriceBook:
    """USD estimates with separate long-context prices and env overrides."""

    # Conservative standard prices per 1M tokens.
    DEFAULTS = {
        "gpt-5.6-luna": (1.00, 6.00),
        "gpt-5.6-terra": (2.50, 15.00),
        "gpt-5.6-sol": (5.00, 30.00),
        "gpt-5.4-mini": (0.75, 4.50),
    }

    # Long-context requests are intentionally estimated at the higher schedule.
    LONG_DEFAULTS = {
        "gpt-5.6-luna": (2.00, 9.00),
        "gpt-5.6-terra": (5.00, 22.50),
        "gpt-5.6-sol": (10.00, 45.00),
    }

    def prices(self, model: str, *, long_context: bool = False) -> tuple[float, float]:
        defaults = self.LONG_DEFAULTS if long_context else self.DEFAULTS
        fallback = (10.00, 45.00) if long_context else (5.00, 30.00)
        default_input, default_output = defaults.get(model, fallback)
        prefix = re.sub(r"[^A-Z0-9]", "_", model.upper())
        suffix = "_LONG" if long_context else ""
        input_price = float(
            os.environ.get(f"ATLAS_PRICE_{prefix}{suffix}_INPUT", default_input)
        )
        output_price = float(
            os.environ.get(f"ATLAS_PRICE_{prefix}{suffix}_OUTPUT", default_output)
        )
        return input_price, output_price

    def estimate(
        self,
        model: str,
        *,
        input_tokens: int,
        output_tokens: int,
        web_calls: int = 0,
        long_context: bool = False,
    ) -> float:
        input_price, output_price = self.prices(model, long_context=long_context)
        web_price = float(os.environ.get("ATLAS_WEB_CALL_USD", "0.01"))
        return (
            max(0, input_tokens) * input_price / 1_000_000
            + max(0, output_tokens) * output_price / 1_000_000
            + max(0, web_calls) * web_price
        )


class BudgetController:
    """Budget guard with an automatic, bounded long-document mode.

    Normal chat remains capped tightly. A request containing an actual input_file
    may exceed the normal 50k cap, up to a hard long-context ceiling. This keeps
    accidental giant chat histories blocked while allowing deliberate PDF/document
    analysis without the old `Input has ...; limit is 50000` failure.
    """

    def __init__(self, store: AtlasStore, client: Any, price_book: PriceBook | None = None) -> None:
        self.store = store
        self.client = client
        self.price_book = price_book or PriceBook()
        self.daily_limit_usd = float(os.environ.get("ATLAS_DAILY_BUDGET_USD", "3.00"))
        self.task_limit_usd = float(os.environ.get("ATLAS_TASK_BUDGET_USD", "0.60"))
        self.max_input_tokens = int(os.environ.get("ATLAS_MAX_INPUT_TOKENS", "50000"))
        self.max_large_input_tokens = int(
            os.environ.get("ATLAS_MAX_LARGE_INPUT_TOKENS", "950000")
        )
        self.large_task_limit_usd = float(
            os.environ.get("ATLAS_LARGE_TASK_BUDGET_USD", "12.00")
        )
        self.large_daily_limit_usd = float(
            os.environ.get("ATLAS_LARGE_DAILY_BUDGET_USD", "20.00")
        )
        self.claude_daily_limit = int(os.environ.get("ATLAS_CLAUDE_DAILY_LIMIT", "3"))

    def count_input_tokens(
        self,
        *,
        model: str,
        input_data: Any,
        instructions: str,
        tools: list[dict[str, Any]],
    ) -> int:
        endpoint = getattr(getattr(self.client, "responses", None), "input_tokens", None)
        counter = getattr(endpoint, "count", None)
        if callable(counter):
            try:
                result = counter(
                    model=model,
                    input=input_data,
                    instructions=instructions,
                    tools=tools,
                )
                value = getattr(result, "input_tokens", None)
                if value is None and isinstance(result, dict):
                    value = result.get("input_tokens")
                if value is not None:
                    return max(1, int(value))
            except Exception:
                pass
        return self._estimate_tokens(input_data, instructions, tools)

    @staticmethod
    def _estimate_tokens(input_data: Any, instructions: str, tools: list[dict[str, Any]]) -> int:
        text = instructions + "\n" + str(input_data) + "\n" + str(tools)
        # UTF-8 byte based fallback is intentionally conservative for Cyrillic.
        return max(1, math.ceil(len(text.encode("utf-8")) / 3))

    @classmethod
    def _contains_input_file(cls, value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("type") == "input_file":
                return True
            return any(cls._contains_input_file(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(cls._contains_input_file(item) for item in value)
        return False

    def reserve(
        self,
        *,
        job_id: str | None,
        model: str,
        input_data: Any,
        instructions: str,
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        use_web: bool,
    ) -> BudgetReservation:
        input_tokens = self.count_input_tokens(
            model=model,
            input_data=input_data,
            instructions=instructions,
            tools=tools,
        )

        large_document = (
            input_tokens > self.max_input_tokens
            and self._contains_input_file(input_data)
        )

        if input_tokens > self.max_input_tokens and not large_document:
            raise BudgetExceeded(
                f"Input has {input_tokens} tokens; normal limit is {self.max_input_tokens}. "
                "Large-input mode is available only for attached documents."
            )
        if large_document and input_tokens > self.max_large_input_tokens:
            raise BudgetExceeded(
                f"Document has {input_tokens} tokens; Atlas long-document limit is "
                f"{self.max_large_input_tokens}. Split the document or analyze it in parts."
            )

        if large_document:
            # One giant file should not be multiplied by the normal four-turn reserve.
            # Follow-up turns reuse the previous response and are typically cached.
            estimated_cost = self.price_book.estimate(
                model,
                input_tokens=math.ceil(input_tokens * 1.20),
                output_tokens=max_output_tokens * 4,
                web_calls=2 if use_web else 0,
                long_context=True,
            )
            daily_limit = self.large_daily_limit_usd
            task_limit = self.large_task_limit_usd
        else:
            # Reserve several response turns because tool loops can issue follow-up calls.
            estimated_cost = self.price_book.estimate(
                model,
                input_tokens=input_tokens * 4,
                output_tokens=max_output_tokens * 9,
                web_calls=2 if use_web else 0,
            )
            daily_limit = self.daily_limit_usd
            task_limit = self.task_limit_usd

        record = self.store.reserve_budget(
            job_id,
            model,
            estimated_cost,
            daily_limit,
            task_limit,
        )
        return BudgetReservation(
            id=record["id"],
            model=model,
            estimated_input_tokens=input_tokens,
            estimated_cost_usd=estimated_cost,
            use_web=use_web,
        )

    def complete(
        self,
        reservation: BudgetReservation,
        *,
        job_id: str | None,
        project_id: str | None,
        model: str,
        input_tokens: int,
        output_tokens: int,
        web_calls: int,
    ) -> float:
        actual_cost = self.price_book.estimate(
            model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            web_calls=web_calls,
            long_context=input_tokens > self.max_input_tokens,
        )
        self.store.complete_budget(
            reservation.id,
            job_id=job_id,
            project_id=project_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            web_calls=web_calls,
            cost_usd=actual_cost,
        )
        return actual_cost

    def release(self, reservation: BudgetReservation | None) -> None:
        self.store.release_budget(reservation.id if reservation else None)

    def allow_claude(self) -> bool:
        return self.store.claude_calls_today() < self.claude_daily_limit

    def record_claude(self, job_id: str | None, project_id: str | None, model: str) -> None:
        self.store.record_claude_call(job_id, project_id, model)

    def status(self) -> dict[str, Any]:
        data = self.store.budget_status(self.daily_limit_usd)
        data.update(
            task_limit_usd=self.task_limit_usd,
            max_input_tokens=self.max_input_tokens,
            large_document={
                "max_input_tokens": self.max_large_input_tokens,
                "task_limit_usd": self.large_task_limit_usd,
                "daily_limit_usd": self.large_daily_limit_usd,
            },
            claude_daily_limit=self.claude_daily_limit,
            claude_calls_today=self.store.claude_calls_today(),
        )
        return data


def response_usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    return int(getattr(usage, "input_tokens", 0) or 0), int(
        getattr(usage, "output_tokens", 0) or 0
    )


def response_web_calls(response: Any) -> int:
    total = 0
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", "")
        if item_type in {"web_search_call", "web_search"}:
            total += 1
    return total
