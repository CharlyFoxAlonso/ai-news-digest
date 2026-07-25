import json
from collections.abc import Callable
from typing import Any

import structlog
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError, field_validator

from ai_news.models import Article, DigestEntry
from ai_news.summary import fallback_summary, validate_summary_text

logger = structlog.get_logger()


class RankingItem(BaseModel):
    article_id: str
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    category: str
    reason: str


class RankingResponse(BaseModel):
    items: list[RankingItem]

    @field_validator("items")
    @classmethod
    def unique_ids(cls, value: list[RankingItem]) -> list[RankingItem]:
        ids = [item.article_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate article IDs")
        return value


class SummaryResponse(BaseModel):
    summary_es: str
    why_it_matters: str

    @field_validator("summary_es")
    @classmethod
    def valid_summary(cls, value: str) -> str:
        return validate_summary_text(value)


Responder = Callable[[str, type[BaseModel]], str]


class GeminiDigestService:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        responder: Responder | None = None,
    ) -> None:
        self.model = model
        self._client = genai.Client(api_key=api_key) if responder is None else None
        self._responder = responder

    def rank(self, candidates: list[Article], limit: int = 5) -> list[Article]:
        if not candidates:
            return []
        by_id = {article.article_id: article for article in candidates}
        try:
            payload = [
                {
                    "article_id": article.article_id,
                    "title": article.title,
                    "description": article.description,
                    "source": article.source_name,
                    "heuristic_score": article.heuristic_score,
                }
                for article in candidates
            ]
            response = RankingResponse.model_validate_json(
                self._generate(_ranking_prompt(payload, limit), RankingResponse)
            )
            if len(response.items) > limit:
                raise ValueError("Gemini selected too many articles")
            unknown = {item.article_id for item in response.items} - by_id.keys()
            if unknown:
                raise ValueError(f"unknown article IDs: {sorted(unknown)}")
            selected: list[Article] = []
            for item in response.items:
                article = by_id[item.article_id]
                article.llm_score = item.score
                article.llm_confidence = item.confidence
                article.category = item.category
                article.ranking_reason = item.reason
                selected.append(article)
            return selected
        except (ValidationError, ValueError, RuntimeError) as exc:
            logger.warning("gemini_ranking_fallback", error=f"{type(exc).__name__}: {exc}")
            return candidates[:limit]

    def summarize(self, article: Article) -> DigestEntry:
        try:
            response = SummaryResponse.model_validate_json(
                self._generate(_summary_prompt(article), SummaryResponse)
            )
            return DigestEntry(
                article=article,
                summary_es=response.summary_es,
                why_it_matters=response.why_it_matters,
                used_fallback=False,
            )
        except (ValidationError, ValueError, RuntimeError) as exc:
            logger.warning(
                "gemini_summary_fallback",
                article_id=article.article_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            return fallback_summary(article)

    def _generate(self, prompt: str, schema: type[BaseModel]) -> str:
        if self._responder is not None:
            return self._responder(prompt, schema)
        if self._client is None:
            raise RuntimeError("Gemini client is unavailable")
        try:
            result = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except Exception as exc:
            # The SDK exposes several transport-specific exceptions; the boundary
            # converts all of them to one treated, observable fallback signal.
            raise RuntimeError(f"Gemini request failed: {type(exc).__name__}") from exc
        if not result.text:
            raise RuntimeError("Gemini returned an empty response")
        return result.text


def _ranking_prompt(payload: list[dict[str, Any]], limit: int) -> str:
    return (
        "Ordena noticias sobre IA y hardware usando solamente los datos entregados. "
        f"Selecciona como máximo {limit}. Devuelve JSON según el schema. "
        "No inventes artículos ni URLs, no cambies IDs, no agregues hechos externos, "
        "no uses conocimiento no suministrado y no repitas IDs.\n"
        f"CANDIDATOS={json.dumps(payload, ensure_ascii=False)}"
    )


def _summary_prompt(article: Article) -> str:
    payload = {
        "article_id": article.article_id,
        "title": article.title,
        "description": article.description,
    }
    return (
        "Resume en español con máximo 3 frases y 320 caracteres. Explica brevemente "
        "por qué importa. Usa solo título y descripción; no agregues datos externos. "
        f"Devuelve JSON según el schema.\nARTICULO={json.dumps(payload, ensure_ascii=False)}"
    )
