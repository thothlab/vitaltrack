from datetime import datetime, timezone

from app.utils.time import (
    days_ago_utc,
    format_user_dt,
    from_user_naive,
    parse_user_datetime,
    to_user_tz,
)


def test_to_user_tz_aware():
    dt = datetime(2026, 4, 16, 10, 0, tzinfo=timezone.utc)
    out = to_user_tz(dt, "Europe/Moscow")
    assert out.hour == 13


def test_parse_user_datetime_hhmm():
    out = parse_user_datetime("21:30", "UTC")
    assert out.tzinfo is not None
    assert out.hour == 21


def test_parse_user_datetime_yesterday():
    out = parse_user_datetime("yesterday 09:00", "UTC")
    assert out.tzinfo is not None


def test_parse_user_datetime_full():
    out = parse_user_datetime("02.04.2026 08:15", "UTC")
    assert out.month == 4 and out.day == 2 and out.hour == 8


def test_format_user_dt_round_trip():
    dt = datetime(2026, 4, 16, 5, 0, tzinfo=timezone.utc)
    s = format_user_dt(dt, "Europe/Moscow", "%H")
    assert s == "08"


def test_days_ago_utc():
    out = days_ago_utc(7, "UTC")
    assert out.tzinfo is not None
