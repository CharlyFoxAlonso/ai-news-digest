from datetime import datetime

from ai_news.models import Article
from ai_news.time_utils import is_within_article_window

POSITIVE_TERMS = {
    "accelerator",
    "agent",
    "artificial intelligence",
    "chip",
    "cuda",
    "foundation model",
    "gpu",
    "inference",
    "large language model",
    "llm",
    "machine learning",
    "npu",
    "pytorch",
    "semiconductor",
    "training",
    "transformer",
}
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
