from datetime import UTC, datetime

from ai_news.filtering import filter_articles
from ai_news.models import Article


def make_article(title: str, description: str = "") -> Article:
    return Article(
        article_id=title,
        source_name="Example",
        source_priority=50,
        is_official_source=False,
        title=title,
        url_original=f"https://example.com/{len(title)}",
        url_canonical=f"https://example.com/{len(title)}",
        published_at_utc=datetime(2026, 7, 25, 10, tzinfo=UTC),
        description=description,
    )


def test_topic_filter_requires_relevance() -> None:
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)
    relevant = make_article("New GPU accelerator for machine learning")
    irrelevant = make_article("Quarterly office renovation")
    assert filter_articles([relevant, irrelevant], now) == [relevant]


def test_negative_terms_outweigh_weak_match() -> None:
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)
    assert filter_articles([make_article("AI coupon giveaway")], now) == []
