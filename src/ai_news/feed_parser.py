import calendar
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
from pydantic import BaseModel, ConfigDict, HttpUrl

from ai_news.sources.base import FeedSource


class ParsedFeedItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: FeedSource
    title: str
    url: HttpUrl
    description: str
    category: str
    published_at_utc: datetime | None

def parse_feed(content: bytes, source: FeedSource, max_entries: int) -> list[ParsedFeedItem]:
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"invalid feed XML: {parsed.bozo_exception}")
    items: list[ParsedFeedItem] = []
    for entry in parsed.entries[:max_entries]:
        link = str(entry.get("link", ""))
        title = str(entry.get("title", "")).strip()
        if not title or not link.startswith(("https://", "http://")):
            continue
        item = ParsedFeedItem(
            source=source,
            title=title,
            url=link,
            description=str(entry.get("summary") or entry.get("description") or ""),
            category=_category(entry),
            published_at_utc=parse_entry_date(entry),
        )
        items.append(item)
    return items


def parse_entry_date(entry: dict[str, Any]) -> datetime | None:
    value: struct_time | None = entry.get("published_parsed") or entry.get("updated_parsed")
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)
    except (OverflowError, TypeError, ValueError):
        return None


def _category(entry: dict[str, Any]) -> str:
    tags = entry.get("tags") or []
    if tags and isinstance(tags[0], dict):
        return str(tags[0].get("term") or "other")
    return "other"
