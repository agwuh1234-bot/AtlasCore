from __future__ import annotations

import os
import re
from typing import Any


MEMORY_POLICY = """
Память Atlas:
- Сохраняй через memory_remember только устойчивые факты: решения, цели, ограничения,
  предпочтения, структуру проекта и незавершённые важные задачи.
- Не сохраняй пароли, API-ключи, токены, платёжные данные и одноразовые коды.
- Перед ответом используй долговременную память и недавнюю историю проекта.
- Если новая информация противоречит старой, уточни или сохрани новое решение,
  не выдавая устаревшее за актуальное.
""".strip()


SHOPIFY_PLAYBOOK = """
Ты работаешь в специализированном режиме Shopify Operator.

Основные правила:
1. Сначала выясни или найди в памяти магазин, рынок, валюту, язык, тему,
   каталог, способы доставки и главную бизнес-цель.
2. Для изменений разделяй работу на: каталог, витрина/тема, контент,
   аналитика, маркетинг, заказы и автоматизация.
3. Любое чтение и анализ можно выполнять автоматически. Перед изменением товара,
   цены, остатков, заказа, темы, домена, скидки или публикацией обязательно
   покажи краткий план и запроси разрешение на запись.
4. Никогда не публикуй тему и не удаляй товар без явного подтверждения.
   Для темы предпочитай draft/preview и сохраняй точку восстановления.
5. Проверяй mobile-first: ширина 390 px, CTA в первом экране, читаемость,
   скорость, изображения, варианты, корзина, checkout, policy pages и SEO.
6. Для карточки товара готовь: ясный заголовок, ценность, преимущества,
   характеристики, доставка/возврат, FAQ, alt-тексты, meta title/description.
7. Для рекламы не выдумывай результаты и отзывы. Отделяй факты от гипотез,
   предлагай измеримые KPI и небольшой безопасный тестовый бюджет.
8. После каждой существенной работы фиксируй: что изменено, где, результат
   проверки, ссылку/идентификатор и способ отката.
9. Если Shopify API ещё не подключён, всё равно подготовь готовые тексты,
   структуру магазина, чек-листы, Liquid/CSS/JSON-код и точные шаги подключения.
""".strip()


SHOPIFY_SEED_MEMORIES = (
    ("role", "Atlas в проекте Shopify работает как осторожный Shopify Operator: mobile-first, измеримо и с точкой отката."),
    ("permission", "Чтение и анализ Shopify разрешены автоматически; цены, товары, заказы, тема, скидки и публикация требуют подтверждения."),
    ("workflow", "Перед публикацией темы использовать draft/preview, проверить мобильный экран, корзину, checkout, SEO и policy pages."),
    ("quality", "Не выдумывать отзывы, продажи и результаты рекламы; факты всегда отделять от гипотез."),
)


SECRET_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|парол|секрет|токен|"
    r"sk-[a-z0-9_-]{8,}|gh[pousr]_[a-z0-9]{8,})",
    flags=re.IGNORECASE,
)


def seed_project_knowledge(store: Any) -> None:
    for kind, content in SHOPIFY_SEED_MEMORIES:
        store.remember("project-shopify", content, kind)


def memory_candidates(text: str) -> list[tuple[str, str]]:
    clean = " ".join((text or "").split()).strip()
    if not clean or len(clean) > 2400 or SECRET_RE.search(clean):
        return []

    lowered = clean.lower()
    rules = (
        ("preference", ("я предпочитаю", "мне удобнее", "всегда делай", "никогда не")),
        ("decision", ("мы решили", "решение:", "фиксируем:", "важное решение")),
        ("goal", ("моя цель", "наша цель", "хочу добиться", "главная цель")),
        ("constraint", ("важно:", "ограничение:", "обязательно", "необходимо учитывать")),
        ("project", ("мой проект", "наш проект", "структура проекта")),
    )
    result: list[tuple[str, str]] = []
    for kind, markers in rules:
        if any(marker in lowered for marker in markers):
            result.append((kind, clean))
            break
    return result


def plugin_registry() -> list[dict[str, Any]]:
    shopify_connected = bool(
        os.environ.get("SHOPIFY_STORE_DOMAIN")
        and os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN")
    )
    return [
        {
            "id": "memory",
            "name": "Долговременная память",
            "description": "Проекты, решения, предпочтения и история в PostgreSQL.",
            "status": "connected",
            "permission": "read-write",
            "requires_confirmation": False,
        },
        {
            "id": "shopify",
            "name": "Shopify Brain",
            "description": (
                "Встроенный Shopify playbook активен."
                if not shopify_connected
                else "Shopify playbook и Admin API подключены."
            ),
            "status": "connected" if shopify_connected else "knowledge-ready",
            "permission": "confirm-writes",
            "requires_confirmation": True,
        },
        {
            "id": "github",
            "name": "GitHub",
            "description": "Чтение репозитория автоматически, запись только с разрешением.",
            "status": "connected" if bool(os.environ.get("GITHUB_TOKEN")) else "disconnected",
            "permission": "confirm-writes",
            "requires_confirmation": True,
        },
        {
            "id": "web",
            "name": "Web Search",
            "description": "Свежая информация включается Model Router автоматически.",
            "status": "available",
            "permission": "read-only",
            "requires_confirmation": False,
        },
        {
            "id": "claude",
            "name": "Claude Review",
            "description": "Независимая проверка сложных решений с дневным лимитом.",
            "status": "connected" if bool(os.environ.get("ANTHROPIC_API_KEY")) else "disconnected",
            "permission": "budgeted",
            "requires_confirmation": False,
        },
    ]


PERMISSION_LEVELS = [
    {
        "id": "read",
        "name": "Чтение",
        "description": "Поиск, диагностика и чтение данных выполняются автоматически.",
        "automatic": True,
        "confirmation": False,
    },
    {
        "id": "safe",
        "name": "Безопасные действия",
        "description": "Анализ, черновики, память и проверки без публикации выполняются автоматически.",
        "automatic": True,
        "confirmation": False,
    },
    {
        "id": "write",
        "name": "Изменение данных",
        "description": "Код, товары, цены, файлы и настройки требуют разового разрешения ✎.",
        "automatic": False,
        "confirmation": True,
    },
    {
        "id": "dangerous",
        "name": "Опасные и дорогие действия",
        "description": "Удаление, публикация, платежи и дорогие операции всегда требуют явного подтверждения.",
        "automatic": False,
        "confirmation": True,
    },
]


def system_registry(storage_backend: str) -> list[dict[str, Any]]:
    """Return non-secret capability diagnostics for the mobile control center."""
    railway_connected = bool(
        os.environ.get("RAILWAY_ENVIRONMENT_ID")
        or os.environ.get("RAILWAY_PROJECT_ID")
        or os.environ.get("RAILWAY_SERVICE_ID")
    )
    checks = [
        ("openai", "OpenAI", bool(os.environ.get("OPENAI_API_KEY")), "Основной интеллект и Model Router"),
        ("github", "GitHub", bool(os.environ.get("GITHUB_TOKEN")), "Репозиторий AtlasCore"),
        ("postgres", "PostgreSQL", storage_backend == "postgres", "Задачи, проекты и долговременная память"),
        ("web", "Web", True, "Свежая публичная информация через Model Router"),
        ("railway", "Railway", railway_connected, "Production-среда AtlasCore"),
        ("claude", "Claude", bool(os.environ.get("ANTHROPIC_API_KEY")), "Независимая проверка сложных решений"),
        (
            "shopify",
            "Shopify",
            bool(os.environ.get("SHOPIFY_STORE_DOMAIN") and os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN")),
            "Admin API; Shopify Brain работает и без подключения",
        ),
        (
            "make",
            "Make",
            bool(os.environ.get("MAKE_API_KEY") or os.environ.get("MAKE_WEBHOOK_URL")),
            "Сценарии автоматизации",
        ),
    ]
    return [
        {
            "id": item_id,
            "name": name,
            "status": "healthy" if connected else "not-configured",
            "connected": connected,
            "detail": detail,
        }
        for item_id, name, connected, detail in checks
    ]
