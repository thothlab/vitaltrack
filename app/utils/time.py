from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def to_user_tz(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz_name))


def from_user_naive(dt_naive: datetime, tz_name: str) -> datetime:
    """Treat a naive datetime as belonging to user TZ; return timezone-aware UTC."""
    return dt_naive.replace(tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc)


def _normalize_time_token(token: str) -> str:
    """Normalize HH<sep>MM where sep is , ; or . — replaces with colon.
    Only matches exactly two digit groups (1-2 and 2 digits) to avoid touching
    date tokens like '15.04.2025'."""
    return re.sub(r'^(\d{1,2})[,;.](\d{2})$', r'\1:\2', token)


def parse_user_datetime(text: str, tz_name: str, default: Optional[datetime] = None) -> datetime:
    """Accept 'today HH:MM', 'yesterday HH:MM', 'HH:MM', 'DD.MM HH:MM',
    'DD.MM.YYYY HH:MM'. Time separator may also be , ; or . (mobile typos)."""
    text = text.strip().lower().replace("  ", " ")
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz=tz).date()

    parts = text.split()
    # Normalize the time token (always the last token)
    if parts:
        parts[-1] = _normalize_time_token(parts[-1])

    try:
        if len(parts) == 1:
            # HH:MM only
            hh, mm = parts[0].split(":")
            d = today
        elif parts[0] in ("today", "сегодня"):
            hh, mm = parts[1].split(":")
            d = today
        elif parts[0] in ("yesterday", "вчера"):
            hh, mm = parts[1].split(":")
            d = today - timedelta(days=1)
        else:
            date_part, time_part = parts
            hh, mm = time_part.split(":")
            chunks = date_part.split(".")
            if len(chunks) == 2:
                day, mon = (int(x) for x in chunks)
                year = today.year
            elif len(chunks) == 3:
                day, mon, year = (int(x) for x in chunks)
                if year < 100:
                    year += 2000
            else:
                raise ValueError("bad date")
            d = today.replace(year=year, month=mon, day=day)
        local = datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=tz)
        return local.astimezone(timezone.utc)
    except (ValueError, IndexError) as exc:
        if default is not None:
            return default
        raise ValueError(f"Cannot parse datetime: {text!r}") from exc


def format_user_dt(dt: datetime, tz_name: str, fmt: str = "%d.%m %H:%M") -> str:
    return to_user_tz(dt, tz_name).strftime(fmt)


def start_of_day(dt: datetime, tz_name: str) -> datetime:
    local = to_user_tz(dt, tz_name).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


def days_ago_utc(days: int, tz_name: str) -> datetime:
    today_local = datetime.now(tz=ZoneInfo(tz_name)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (today_local - timedelta(days=days)).astimezone(timezone.utc)
