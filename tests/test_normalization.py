from datetime import UTC, datetime

import pytest

from ai_news.feed_parser import ParsedFeedItem
from ai_news.normalization import article_from_feed, canonicalize_url, clean_html, normalize_title
from ai_news.sources.base import FeedSource


def test_clean_html_and_length_limit() -> None:
    assert clean_html("<p>Hello&nbsp; <b>GPU</b></p>") == "Hello GPU"
    assert clean_html("<p>" + ("x" * 50) + "</p>", 10) == "x" * 10


def test_url_canonicalization_removes_tracking_but_keeps_identifiers() -> None:
    actual = canonicalize_url(
        "HTTPS://Example.COM/post/?utm_source=x&id=42&lang=en&fbclid=y#section"
    )
    assert actual == "https://example.com/post?id=42&lang=en"


def test_invalid_scheme_is_rejected() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        canonicalize_url("javascript:alert(1)")


def test_article_id_is_deterministic() -> None:
    item = ParsedFeedItem(
        source=FeedSource("Source", "https://example.com/feed", 10),
        title="  AI   release  ",
        url="https://example.com/a?utm_medium=email",
        description="<b>News</b>",
        category="AI",
        published_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
    )
    first = article_from_feed(item)
    second = article_from_feed(item)
    assert first is not None and second is not None
    assert first.article_id == second.article_id
    assert normalize_title(item.title) == "AI release"
