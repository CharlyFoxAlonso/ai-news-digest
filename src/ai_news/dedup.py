import re
from collections.abc import Iterable

from rapidfuzz.fuzz import token_set_ratio

from ai_news.models import Article

SIMILARITY_THRESHOLD = 88
GENERIC_TOKENS = {"ai", "model", "release", "update", "nvidia", "gpu", "new", "the"}


def deduplicate(articles: Iterable[Article]) -> list[Article]:
    selected: list[Article] = []
    for candidate in sorted(articles, key=_preference_key):
        if not any(_same_event(candidate, existing) for existing in selected):
            selected.append(candidate)
    return selected


def _same_event(left: Article, right: Article) -> bool:
    if str(left.url_canonical) == str(right.url_canonical):
        return True
    left_title = _title_key(left.title)
    right_title = _title_key(right.title)
    if left_title == right_title:
        return True
    distinctive_overlap = _distinctive_tokens(left_title) & _distinctive_tokens(right_title)
    return (
        len(distinctive_overlap) >= 2
        and token_set_ratio(left_title, right_title) >= SIMILARITY_THRESHOLD
    )


def _preference_key(article: Article) -> tuple[int, int, object]:
    return (-int(article.is_official_source), -article.source_priority, article.published_at_utc)


def _title_key(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9][a-z0-9.+-]*", title.casefold()))


def _distinctive_tokens(title: str) -> set[str]:
    return {token for token in title.split() if token not in GENERIC_TOKENS and len(token) >= 3}
