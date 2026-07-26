from datetime import UTC, datetime

import pytest

import ai_news.filtering as filtering
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


@pytest.mark.parametrize(
    "title",
    [
        "OpenAI releases a new model",
        "Anthropic announces a benchmark",
        "Claude gains a coding feature",
        "DeepSeek launches a reasoning model",
        "Mistral unveils a new assistant",
        "Perplexity introduces a research mode",
        "Moonshot AI presents a new model",
        "Kimi reaches a new benchmark",
        "ElevenLabs releases a voice model",
        "Runway announces a video model",
    ],
)
def test_configured_ai_entities_are_relevant(title: str) -> None:
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)
    article = make_article(title)
    assert filter_articles([article], now) == [article]


@pytest.mark.parametrize(
    "title",
    [
        "Quarterly office renovation",
        "Coupon giveaway for subscribers",
        "Weekend horoscope predictions",
        "Smartphone case review",
        "Local football results",
    ],
)
def test_unrelated_titles_remain_irrelevant(title: str) -> None:
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)
    assert filter_articles([make_article(title)], now) == []


def test_topic_config_requires_both_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(filtering.tomllib, "loads", lambda _contents: {})
    with pytest.raises(ValueError, match="missing group"):
        filtering._load_positive_terms()


def test_topic_config_requires_string_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    config = {"concepts": {"terms": ["valid"]}, "entities": {"terms": [1]}}
    monkeypatch.setattr(filtering.tomllib, "loads", lambda _contents: config)
    with pytest.raises(ValueError, match="invalid terms"):
        filtering._load_positive_terms()
