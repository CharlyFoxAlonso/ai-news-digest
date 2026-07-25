from datetime import UTC, datetime, timedelta

from ai_news.dedup import deduplicate
from ai_news.models import Article


def article(
    article_id: str,
    title: str,
    url: str,
    *,
    official: bool = False,
    priority: int = 50,
    minutes: int = 0,
) -> Article:
    return Article(
        article_id=article_id,
        source_name=article_id,
        source_priority=priority,
        is_official_source=official,
        title=title,
        url_original=url,
        url_canonical=url,
        published_at_utc=datetime(2026, 7, 25, tzinfo=UTC) + timedelta(minutes=minutes),
    )


def test_deduplicates_url_and_prefers_official_source() -> None:
    unofficial = article("press", "Model Z launch", "https://example.com/z", priority=90)
    official = article("vendor", "Model Z is launched", "https://example.com/z", official=True)
    assert deduplicate([unofficial, official]) == [official]


def test_similar_titles_for_same_event_are_deduplicated() -> None:
    first = article("a", "Acme launches Falcon 3.2 inference accelerator", "https://a.example/x")
    second = article("b", "Acme launches its Falcon 3.2 accelerator for inference", "https://b.example/x")
    assert len(deduplicate([first, second])) == 1


def test_generic_shared_terms_do_not_create_false_positive() -> None:
    first = article("a", "NVIDIA GPU update for desktop drivers", "https://a.example/x")
    second = article("b", "NVIDIA GPU update for cloud pricing", "https://b.example/x")
    assert len(deduplicate([first, second])) == 2
