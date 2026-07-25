import json
from datetime import UTC, datetime

from ai_news.llm.gemini import GeminiDigestService
from ai_news.models import Article


def article(article_id: str = "known") -> Article:
    return Article(
        article_id=article_id,
        source_name="Source",
        source_priority=80,
        is_official_source=True,
        title="Model X improves AI inference",
        url_original=f"https://example.com/{article_id}",
        url_canonical=f"https://example.com/{article_id}",
        published_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
        description="Model X improves inference throughput.",
        heuristic_score=80,
    )


def responder(value):
    return lambda _prompt, _schema: value


def test_valid_ranking_json() -> None:
    payload = json.dumps(
        {"items": [{"article_id": "known", "score": 91, "confidence": 0.9, "category": "AI", "reason": "Concrete release"}]}
    )
    item = article()
    ranked = GeminiDigestService("x", "model", responder=responder(payload)).rank([item])
    assert ranked == [item]
    assert item.llm_score == 91


def test_invalid_json_and_unknown_ids_use_heuristic_fallback() -> None:
    item = article()
    assert GeminiDigestService("x", "model", responder=responder("{")).rank([item]) == [item]
    unknown = json.dumps(
        {"items": [{"article_id": "invented", "score": 90, "confidence": 1, "category": "AI", "reason": "x"}]}
    )
    assert GeminiDigestService("x", "model", responder=responder(unknown)).rank([item]) == [item]


def test_duplicate_ids_use_fallback() -> None:
    ranked_item = {"article_id": "known", "score": 90, "confidence": 1, "category": "AI", "reason": "x"}
    payload = json.dumps({"items": [ranked_item, ranked_item]})
    item = article()
    assert GeminiDigestService("x", "model", responder=responder(payload)).rank([item]) == [item]


def test_valid_and_invalid_summary() -> None:
    item = article()
    valid = json.dumps({"summary_es": "Mejora la inferencia.", "why_it_matters": "Reduce costos."})
    entry = GeminiDigestService("x", "model", responder=responder(valid)).summarize(item)
    assert not entry.used_fallback
    too_long = json.dumps({"summary_es": "x" * 321, "why_it_matters": "x"})
    fallback = GeminiDigestService("x", "model", responder=responder(too_long)).summarize(item)
    assert fallback.used_fallback


def test_too_many_sentences_use_fallback() -> None:
    payload = json.dumps({"summary_es": "Uno. Dos. Tres. Cuatro.", "why_it_matters": "x"})
    assert GeminiDigestService("x", "model", responder=responder(payload)).summarize(article()).used_fallback
