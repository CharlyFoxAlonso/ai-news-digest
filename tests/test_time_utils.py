from datetime import UTC, datetime, timedelta

import pytest

from ai_news.time_utils import digest_date, is_within_article_window, to_utc


def test_buenos_aires_date_conversion() -> None:
    assert digest_date(datetime(2026, 7, 25, 2, 30, tzinfo=UTC)).isoformat() == "2026-07-24"


def test_exact_24_hour_boundary_is_included() -> None:
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)
    assert is_within_article_window(now - timedelta(hours=24), now)
    assert not is_within_article_window(now - timedelta(hours=24, microseconds=1), now)
    assert not is_within_article_window(now + timedelta(microseconds=1), now)


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_utc(datetime(2026, 1, 1))
