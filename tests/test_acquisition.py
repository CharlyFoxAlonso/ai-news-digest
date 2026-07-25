import httpx
import pytest

from ai_news.acquisition import acquire_feeds
from ai_news.sources.base import FeedSource


@pytest.mark.asyncio
async def test_source_failure_is_isolated(fixtures_dir) -> None:
    good = FeedSource("Good", "https://example.com/good", 10)
    bad = FeedSource("Bad", "https://example.com/bad", 10)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bad":
            return httpx.Response(503)
        return httpx.Response(200, content=(fixtures_dir / "sample_feed.xml").read_bytes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await acquire_feeds(
            (good, bad), timeout_seconds=1, max_bytes=1_000_000, max_entries=10, client=client
        )
    assert len(results[0].items) == 1
    assert "503" in (results[1].error or "")


@pytest.mark.asyncio
async def test_oversized_feed_is_rejected() -> None:
    source = FeedSource("Large", "https://example.com/large", 10)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 100))
    async with httpx.AsyncClient(transport=transport) as client:
        [result] = await acquire_feeds(
            (source,), timeout_seconds=1, max_bytes=50, max_entries=10, client=client
        )
    assert "FeedTooLargeError" in (result.error or "")
