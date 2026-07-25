import re

from ai_news.models import Article, DigestEntry
from ai_news.normalization import clean_html

MAX_SUMMARY_LENGTH = 320


def fallback_summary(article: Article) -> DigestEntry:
    base = clean_html(article.description, MAX_SUMMARY_LENGTH)
    summary = base or article.title
    return DigestEntry(
        article=article,
        summary_es=_safe_truncate(summary, MAX_SUMMARY_LENGTH),
        why_it_matters="Fuente RSS seleccionada por relevancia temática y ranking determinista.",
        used_fallback=True,
    )


def validate_summary_text(value: str) -> str:
    cleaned = clean_html(value, MAX_SUMMARY_LENGTH + 1)
    if len(cleaned) > MAX_SUMMARY_LENGTH:
        raise ValueError("summary exceeds 320 characters")
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", cleaned) if part]
    if len(sentences) > 3:
        raise ValueError("summary exceeds three sentences")
    return cleaned


def _safe_truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    shortened = value[: limit - 1].rsplit(" ", 1)[0]
    return f"{shortened or value[: limit - 1]}…"
