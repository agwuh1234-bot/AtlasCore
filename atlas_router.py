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
    def __init__(self) -> None:
        self.fast_model = os.environ.get("ATLAS_MODEL_FAST", "gpt-5.6-luna")
        self.document_model = os.environ.get("ATLAS_MODEL_DOCUMENT", "gpt-5.6-terra")
        self.strong_model = os.environ.get("ATLAS_MODEL_STRONG", "gpt-5.6-sol")
        self.fallback_model = os.environ.get("ATLAS_MODEL_FALLBACK", "gpt-5.4-mini")

    def select(self, text: str, *, has_attachments: bool = False, claude_review: bool = False) -> RouteDecision:
        lowered = (text or "").lower()
        use_web = self._needs_fresh_information(lowered)
        strong = self._needs_strong_model(lowered, has_attachments=has_attachments, claude_review=claude_review)
        if strong:
            return RouteDecision("strong", self.strong_model, use_web, "code_or_complex_reasoning")
        if has_attachments:
            return RouteDecision("document", self.document_model, use_web, "attachment_analysis")
        if use_web:
            return RouteDecision("fresh", self.fast_model, True, "fresh_information")
        return RouteDecision("fast", self.fast_model, False, "routine_request")

    @staticmethod
    def _needs_fresh_information(text: str) -> bool:
        terms = ("сегодня", "сейчас", "последн", "свеж", "новост", "актуальн", "текущ", "цена", "курс", "погода", "расписан", "кто сейчас", "latest", "today", "current", "recent", "news", "price", "weather", "schedule", "search the web", "найди в интернете", "проверь в интернете")
        return any(term in text for term in terms)

    @staticmethod
    def _needs_strong_model(text: str, *, has_attachments: bool, claude_review: bool) -> bool:
        if claude_review:
            return True
        terms = ("код", "репозитор", "архитект", "рефактор", "отлад", "debug", "python", "javascript", "typescript", "sql", "api", "deploy", "railway", "github", "тест", "ошибк", "сложн", "сравни варианты", "план миграции", "security", "безопасност", "code", "architecture", "implement", "fix", "reason step")
        return any(term in text for term in terms) or len(text) > 2500

    def public_config(self) -> dict[str, str]:
        return {"fast": self.fast_model, "document": self.document_model, "strong": self.strong_model, "fallback": self.fallback_model}


class PriceBook:
    DEFAULTS = {"gpt-5.6-luna": (1.00, 6.00), "gpt-5.6-terra": (2.50, 15.00), "gpt-5.6-sol": (5.00, 30.00), "gpt-5.4-mini": (0.75, 4.50)}
    LONG_DEFAULTS = {"gpt-5.6-luna": (2.00, 9.00), "gpt-5.6-terra": (5.00, 22.50), "gpt-5.6-sol": (10.00, 45.00)}

    def prices(self, model: str, *, long_context: bool = False) -> tuple[float, float]:
        defaults = self.LONG_DEFAULTS if long_context else self.DEFAULTS
        fallback = (10.00, 45.00) if long_context else (5.00, 30.00)
        default_input, default_output = defaults.get(model, fallback)
        prefix = re.sub(r"[^A-Z0-9]", "_", model.upper())
        suffix = "_LONG" if long_context else ""
        return (float(os.environ.get(f"ATLAS_PRICE_{prefix}{suffix}_INPUT", default_input)), float(os.environ.get(f"ATLAS_PRICE_{prefix}{suffix}_OUTPUT", default_output)))

    def estimate(self, model: str, *, input_tokens: int, output_tokens: int, web_calls: int = 0, long_context: bool = False) -> float:
        input_price, output_price = self.prices(model, long_context=long_context)
        web_price = float(os.environ.get("ATLAS_WEB_CALL_USD", "0.01"))
        return max(0, input_tokens) * input_price / 1_000_000 + max(0, output_tokens) * output_price / 1_000_000 + max(0, web_calls) * web_price


class BudgetController:
    """Usage accounting plus input-size safety.

    Monetary caps are disabled by default. Set ATLAS_BUDGET_ENFORCED=1 to restore
    daily/per-task guards. Input context ceilings remain enforced because they are
    technical model limits rather than spending limits.
    """

    def __init__(self, store: AtlasStore, client: Any, price_book: PriceBook | None = None) -> None:
        self.store = store
        self.client = client
        self.price_book = price_book or PriceBook()
        self.budget_enforced = os.environ.get("ATLAS_BUDGET_ENFORCED", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.daily_limit_usd = float(os.environ.get("ATLAS_DAILY_BUDGET_USD", "3.00"))
        self.task_limit_usd = float(os.environ.get("ATLAS_TASK_BUDGET_USD", "0.60"))
        self.max_input_tokens = int(os.environ.get("ATLAS_MAX_INPUT_TOKENS", "50000"))
        self.max_large_input_tokens = int(os.environ.get("ATLAS_MAX_LARGE_INPUT_TOKENS", "950000"))
        self.large_task_limit_usd = float(os.environ.get("ATLAS_LARGE_TASK_BUDGET_USD", "12.00"))
        self.large_daily_limit_usd = float(os.environ.get("ATLAS_LARGE_DAILY_BUDGET_USD", "20.00"))
        self.claude_daily_limit = int(os.environ.get("ATLAS_CLAUDE_DAILY_LIMIT", "3"))

    def count_input_tokens(self, *, model: str, input_data: Any, instructions: str, tools: list[dict[str, Any]]) -> int:
        endpoint = getattr(getattr(self.client, "responses", None), "input_tokens", None)
        counter = getattr(endpoint, "count", None)
        if callable(counter):
            try:
                result = counter(model=model, input=input_data, instructions=instructions, tools=tools)
                value = getattr(result, "input_tokens", None)
                if value is None and isinstance(result, dict): value = result.get("input_tokens")
                if value is not None: return max(1, int(value))
            except Exception: pass
        return self._estimate_tokens(input_data, instructions, tools)

    @staticmethod
    def _estimate_tokens(input_data: Any, instructions: str, tools: list[dict[str, Any]]) -> int:
        return max(1, math.ceil(len((instructions + "\n" + str(input_data) + "\n" + str(tools)).encode("utf-8")) / 3))

    @classmethod
    def _contains_input_file(cls, value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("type") == "input_file": return True
            return any(cls._contains_input_file(item) for item in value.values())
        if isinstance(value, (list, tuple)): return any(cls._contains_input_file(item) for item in value)
        return False

    def reserve(self, *, job_id: str | None, model: str, input_data: Any, instructions: str, tools: list[dict[str, Any]], max_output_tokens: int, use_web: bool) -> BudgetReservation:
        input_tokens = self.count_input_tokens(model=model, input_data=input_data, instructions=instructions, tools=tools)
        large_document = input_tokens > self.max_input_tokens and self._contains_input_file(input_data)
        if input_tokens > self.max_input_tokens and not large_document:
            raise BudgetExceeded(f"Input has {input_tokens} tokens; normal limit is {self.max_input_tokens}. Large-input mode is available only for attached documents.")
        if large_document and input_tokens > self.max_large_input_tokens:
            raise BudgetExceeded(f"Document has {input_tokens} tokens; Atlas long-document limit is {self.max_large_input_tokens}. Split the document or analyze it in parts.")

        if large_document:
            estimated_cost = self.price_book.estimate(model, input_tokens=math.ceil(input_tokens * 1.20), output_tokens=max_output_tokens * 4, web_calls=2 if use_web else 0, long_context=True)
            daily_limit, task_limit = self.large_daily_limit_usd, self.large_task_limit_usd
        else:
            estimated_cost = self.price_book.estimate(model, input_tokens=input_tokens * 4, output_tokens=max_output_tokens * 9, web_calls=2 if use_web else 0)
            daily_limit, task_limit = self.daily_limit_usd, self.task_limit_usd

        # Keep accounting records while disabling monetary rejection. AtlasStore treats
        # very large limits as normal finite numbers, so no DB schema change is needed.
        if not self.budget_enforced:
            daily_limit = 1_000_000_000.0
            task_limit = 1_000_000_000.0
        record = self.store.reserve_budget(job_id, model, estimated_cost, daily_limit, task_limit)
        return BudgetReservation(record["id"], model, input_tokens, estimated_cost, use_web)

    def complete(self, reservation: BudgetReservation, *, job_id: str | None, project_id: str | None, model: str, input_tokens: int, output_tokens: int, web_calls: int) -> float:
        actual_cost = self.price_book.estimate(model, input_tokens=input_tokens, output_tokens=output_tokens, web_calls=web_calls, long_context=input_tokens > self.max_input_tokens)
        self.store.complete_budget(reservation.id, job_id=job_id, project_id=project_id, model=model, input_tokens=input_tokens, output_tokens=output_tokens, web_calls=web_calls, cost_usd=actual_cost)
        return actual_cost

    def release(self, reservation: BudgetReservation | None) -> None:
        self.store.release_budget(reservation.id if reservation else None)

    def allow_claude(self) -> bool:
        return self.store.claude_calls_today() < self.claude_daily_limit

    def record_claude(self, job_id: str | None, project_id: str | None, model: str) -> None:
        self.store.record_claude_call(job_id, project_id, model)

    def status(self) -> dict[str, Any]:
        status_limit = self.daily_limit_usd if self.budget_enforced else 1_000_000_000.0
        data = self.store.budget_status(status_limit)
        data.update(budget_enforced=self.budget_enforced, task_limit_usd=self.task_limit_usd if self.budget_enforced else None, max_input_tokens=self.max_input_tokens, large_document={"max_input_tokens": self.max_large_input_tokens, "task_limit_usd": self.large_task_limit_usd if self.budget_enforced else None, "daily_limit_usd": self.large_daily_limit_usd if self.budget_enforced else None}, claude_daily_limit=self.claude_daily_limit, claude_calls_today=self.store.claude_calls_today())
        return data


def response_usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None: return 0, 0
    if isinstance(usage, dict): return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)


def response_web_calls(response: Any) -> int:
    return sum(1 for item in getattr(response, "output", []) or [] if getattr(item, "type", "") in {"web_search_call", "web_search"})
