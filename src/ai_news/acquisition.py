import asyncio
from dataclasses import dataclass, field
from time import perf_counter

import httpx
import structlog

from ai_news.feed_parser import ParsedFeedItem, parse_feed
from ai_news.sources.base import FeedSource

logger = structlog.get_logger()


@dataclass(slots=True)
class FeedResult:
    source: FeedSource
    items: list[ParsedFeedItem] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None


class FeedTooLargeError(ValueError):
    pass


async def acquire_feeds(
    sources: tuple[FeedSource, ...],
    *,
    timeout_seconds: float,
    max_bytes: int,
    max_entries: int,
    client: httpx.AsyncClient | None = None,
) -> list[FeedResult]:
    owns_client = client is None
    active_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=True,
        headers={"User-Agent": "ai-news-digest/0.1 (+public portfolio project)"},
    )
    try:
        return list(
            await asyncio.gather(
                *(
                    _fetch_one(active_client, source, max_bytes=max_bytes, max_entries=max_entries)
                    for source in sources
                )
            )
        )
    finally:
        if owns_client:
            await active_client.aclose()


async def _fetch_one(
    client: httpx.AsyncClient,
    source: FeedSource,
    *,
    max_bytes: int,
    max_entries: int,
) -> FeedResult:
    started = perf_counter()
    try:
        async with client.stream("GET", source.url) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise FeedTooLargeError(f"feed exceeds {max_bytes} bytes")
                chunks.append(chunk)
        items = parse_feed(b"".join(chunks), source, max_entries)
        result = FeedResult(source=source, items=items)
    except (httpx.HTTPError, ValueError) as exc:
        result = FeedResult(source=source, error=f"{type(exc).__name__}: {exc}")
    result.duration_ms = round((perf_counter() - started) * 1000)
    logger.info(
        "feed_acquired",
        source=source.name,
        duration_ms=result.duration_ms,
        article_count=len(result.items),
        success=result.error is None,
        error=result.error,
    )
    return result
