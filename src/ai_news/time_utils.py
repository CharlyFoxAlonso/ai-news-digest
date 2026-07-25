from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

BUENOS_AIRES = ZoneInfo("America/Argentina/Buenos_Aires")
ARTICLE_WINDOW = timedelta(hours=24)


def utc_now() -> datetime:
    return datetime.now(UTC)


def digest_date(now_utc: datetime, timezone: ZoneInfo = BUENOS_AIRES) -> date:
    return _aware_utc(now_utc).astimezone(timezone).date()


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def is_within_article_window(published_at: datetime, now_utc: datetime) -> bool:
    """Include the exact 24-hour lower boundary and exclude future timestamps."""
    published = to_utc(published_at)
    now = _aware_utc(now_utc)
    return now - ARTICLE_WINDOW <= published <= now


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    return value.astimezone(UTC)
