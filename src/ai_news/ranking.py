import re
from datetime import UTC, datetime

from ai_news.filtering import topic_relevance
from ai_news.models import Article

MAX_LLM_CANDIDATES = 15
VERSION_PATTERN = re.compile(r"\b(?:v?\d+(?:\.\d+)+|[A-Z][A-Za-z]+-\d+)\b")
PROMOTIONAL = {"amazing", "revolutionary", "game-changing", "unmissable"}
VAGUE = {"big news", "our latest update", "what's new", "announcement"}


def rank_heuristically(
    articles: list[Article], now_utc: datetime, limit: int = MAX_LLM_CANDIDATES
) -> list[Article]:
    now = now_utc.astimezone(UTC)
    for article in articles:
        age_hours = max(0.0, (now - article.published_at_utc.astimezone(UTC)).total_seconds() / 3600)
        title_lower = article.title.casefold()
        score = article.source_priority * 0.28
        score += 12 if article.is_official_source else 0
        score += max(0.0, 14 - age_hours * 0.5)
        score += min(18, topic_relevance(article) * 3)
        score += 6 if VERSION_PATTERN.search(article.title) else 0
        score += 4 if 35 <= len(article.title) <= 120 else 0
        score += min(6, len(article.description) / 100)
        score -= 9 if any(term in title_lower for term in PROMOTIONAL) else 0
        score -= 8 if any(term in title_lower for term in VAGUE) else 0
        article.heuristic_score = round(max(0.0, min(100.0, score)), 2)
    return sorted(articles, key=lambda item: (-item.heuristic_score, item.article_id))[:limit]
