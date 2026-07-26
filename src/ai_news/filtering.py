import tomllib
from datetime import datetime
from pathlib import Path

from ai_news.models import Article
from ai_news.time_utils import is_within_article_window


def _load_positive_terms() -> frozenset[str]:
    config_path = Path(__file__).with_name("topics.toml")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    terms: list[str] = []
    for group_name in ("concepts", "entities"):
        group = config.get(group_name)
        if not isinstance(group, dict):
            raise ValueError(f"topics configuration missing group: {group_name}")
        group_terms = group.get("terms")
        if not isinstance(group_terms, list) or not all(
            isinstance(term, str) for term in group_terms
        ):
            raise ValueError(f"topics configuration has invalid terms: {group_name}")
        terms.extend(group_terms)
    return frozenset(term.casefold() for term in terms)


POSITIVE_TERMS = _load_positive_terms()
NEGATIVE_TERMS = {"coupon", "giveaway", "horoscope", "smartphone case"}
TECHNICAL_SOURCES = {"OpenAI", "Google AI", "Hugging Face", "NVIDIA Developer", "Apple Machine Learning"}


def topic_relevance(article: Article) -> int:
    haystack = " ".join(
        (article.title, article.description, article.category, article.source_name)
    ).casefold()
    positive = sum(term in haystack for term in POSITIVE_TERMS)
    negative = sum(term in haystack for term in NEGATIVE_TERMS)
    context_bonus = int(article.source_name in TECHNICAL_SOURCES and positive > 0)
    return positive + context_bonus - (negative * 3)


def filter_articles(articles: list[Article], now_utc: datetime) -> list[Article]:
    return [
        article
        for article in articles
        if is_within_article_window(article.published_at_utc, now_utc)
        and topic_relevance(article) >= 1
    ]
