from datetime import UTC, datetime

from ai_news.feed_parser import parse_feed
from ai_news.sources.base import FeedSource


def test_rss_and_atom_dates(fixtures_dir) -> None:
    source = FeedSource("Fixture", "https://example.com/feed", 50)
    rss = parse_feed((fixtures_dir / "sample_feed.xml").read_bytes(), source, 10)
    atom = parse_feed((fixtures_dir / "sample_atom.xml").read_bytes(), source, 10)
    assert rss[0].published_at_utc == datetime(2026, 7, 24, 12, tzinfo=UTC)
    assert atom[0].published_at_utc == datetime(2026, 7, 24, 13, 30, tzinfo=UTC)


def test_invalid_date_is_preserved_as_none() -> None:
    xml = b"""<rss><channel><item><title>AI</title>
    <link>https://example.com/a</link><pubDate>not-a-date</pubDate>
    </item></channel></rss>"""
    item = parse_feed(xml, FeedSource("Test", "https://example.com/feed", 1), 10)[0]
    assert item.published_at_utc is None


def test_entry_limit(fixtures_dir) -> None:
    source = FeedSource("Fixture", "https://example.com/feed", 50)
    assert parse_feed((fixtures_dir / "sample_feed.xml").read_bytes(), source, 0) == []
