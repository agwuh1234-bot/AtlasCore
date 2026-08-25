from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


FREQUENCIES = {"once", "daily", "weekly"}
DEFAULT_TIMEZONE = "Europe/Berlin"


class ScheduleValidationError(ValueError):
    pass


def _zone(value: str) -> ZoneInfo:
    name = (value or DEFAULT_TIMEZONE).strip()[:80]
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ScheduleValidationError("Unknown timezone") from exc


def _clock(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = (value or "").split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (TypeError, ValueError) as exc:
        raise ScheduleValidationError("Time must use HH:MM") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ScheduleValidationError("Time must use HH:MM")
    return hour, minute


def normalize_schedule(
    *,
    frequency: str,
    timezone_name: str = DEFAULT_TIMEZONE,
    time_local: str = "09:00",
    weekdays: list[int] | None = None,
    run_at: str | None = None,
) -> dict[str, Any]:
    frequency = (frequency or "").strip().lower()
    if frequency not in FREQUENCIES:
        raise ScheduleValidationError("Frequency must be once, daily or weekly")
    zone = _zone(timezone_name)
    clean: dict[str, Any] = {
        "frequency": frequency,
        "timezone": zone.key,
        "time_local": time_local,
        "weekdays": [],
        "run_at": None,
    }
    if frequency == "once":
        if not run_at:
            raise ScheduleValidationError("run_at is required for a one-time schedule")
        try:
            parsed = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ScheduleValidationError("Invalid run_at") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        clean["run_at"] = parsed.astimezone(timezone.utc).isoformat()
        return clean

    hour, minute = _clock(time_local)
    clean["time_local"] = f"{hour:02d}:{minute:02d}"
    if frequency == "weekly":
        days = sorted({int(day) for day in (weekdays or []) if 0 <= int(day) <= 6})
        if not days:
            raise ScheduleValidationError("Choose at least one weekday")
        clean["weekdays"] = days
    return clean


def next_run_at(config: dict[str, Any], after_ts: float) -> float | None:
    frequency = str(config.get("frequency") or "")
    zone = _zone(str(config.get("timezone") or DEFAULT_TIMEZONE))
    after = datetime.fromtimestamp(float(after_ts), timezone.utc)

    if frequency == "once":
        run_at = config.get("run_at")
        if not run_at:
            return None
        parsed = datetime.fromisoformat(str(run_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        candidate = parsed.astimezone(timezone.utc)
        return candidate.timestamp() if candidate > after else None

    hour, minute = _clock(str(config.get("time_local") or "09:00"))
    local_after = after.astimezone(zone)

    if frequency == "daily":
        candidate = local_after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= local_after:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc).timestamp()

    if frequency == "weekly":
        weekdays = {int(day) for day in config.get("weekdays") or []}
        for offset in range(0, 8):
            day = local_after.date() + timedelta(days=offset)
            if day.weekday() not in weekdays:
                continue
            candidate = datetime(
                day.year, day.month, day.day, hour, minute, tzinfo=zone
            )
            if candidate > local_after:
                return candidate.astimezone(timezone.utc).timestamp()
        return None

    raise ScheduleValidationError("Unsupported schedule frequency")
