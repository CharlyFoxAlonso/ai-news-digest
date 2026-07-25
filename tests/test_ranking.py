from datetime import UTC, datetime, timedelta

from ai_news.models import Article
from ai_news.ranking import rank_heuristically


def make_article(article_id: str, title: str, priority: int, official: bool) -> Article:
    return Article(
        article_id=article_id,
        source_name="OpenAI" if official else "News",
        source_priority=priority,
        is_official_source=official,
        title=title,
        url_original=f"https://example.com/{article_id}",
        url_canonical=f"https://example.com/{article_id}",
        published_at_utc=datetime(2026, 7, 25, 11, tzinfo=UTC),
        description="Technical details for machine learning inference on GPU hardware.",
    )


def test_heuristic_ranking_is_deterministic_and_limited() -> None:
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)
    official = make_article("a", "Acme Model 3.2 improves GPU inference", 90, True)
    vague = make_article("b", "Our latest update", 50, False)
    ranked = rank_heuristically([vague, official], now, limit=1)
    assert ranked == [official]
    assert official.heuristic_score > vague.heuristic_score


def test_recency_affects_score() -> None:
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)
    recent = make_article("a", "GPU inference toolkit", 50, False)
    old = make_article("b", "GPU inference toolkit", 50, False)
    old.published_at_utc -= timedelta(hours=20)
    rank_heuristically([old, recent], now)
    assert recent.heuristic_score > old.heuristic_score
