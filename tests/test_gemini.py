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


def test_invalid_json_uses_heuristic_fallback() -> None:
    item = article()
    assert GeminiDigestService("x", "model", responder=responder("{")).rank([item]) == [item]


def test_duplicate_ids_are_removed_and_unknown_ids_are_ignored() -> None:
    known = article()
    second = article("second")
    ranked_item = {
        "article_id": "known",
        "score": 90,
        "confidence": 1,
        "category": "AI",
        "reason": "x",
    }
    unknown = ranked_item | {"article_id": "invented"}
    payload = json.dumps({"items": [ranked_item, ranked_item, unknown]})
    assert GeminiDigestService("x", "model", responder=responder(payload)).rank(
        [known, second]
    ) == [known]


def test_only_unknown_ids_use_heuristic_fallback() -> None:
    item = article()
    unknown = {
        "article_id": "invented",
        "score": 90,
        "confidence": 1,
        "category": "AI",
        "reason": "x",
    }
    payload = json.dumps({"items": [unknown]})
    assert GeminiDigestService("x", "model", responder=responder(payload)).rank([item]) == [item]


def test_ranking_never_returns_more_than_limit() -> None:
    candidates = [article(str(index)) for index in range(7)]
    items = [
        {
            "article_id": item.article_id,
            "score": 90 - index,
            "confidence": 1,
            "category": "AI",
            "reason": "x",
        }
        for index, item in enumerate(candidates)
    ]
    payload = json.dumps({"items": items})
    assert GeminiDigestService("x", "model", responder=responder(payload)).rank(
        candidates, limit=5
    ) == candidates[:5]


def test_empty_selection_remains_empty() -> None:
    payload = json.dumps({"items": []})
    assert GeminiDigestService("x", "model", responder=responder(payload)).rank(
        [article()]
    ) == []


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
