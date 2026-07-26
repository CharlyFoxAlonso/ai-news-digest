import json
from collections.abc import Callable
from typing import Any

import structlog
from google import genai
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
            returned_ids = [item.article_id for item in response.items]
            logger.info(
                "gemini_ranking_response",
                returned_article_ids=returned_ids,
                returned_count=len(returned_ids),
            )
            selected: list[Article] = []
            seen_ids: set[str] = set()
            for item in response.items:
                if item.article_id in seen_ids:
                    continue
                seen_ids.add(item.article_id)
                article = by_id.get(item.article_id)
                if article is None:
                    continue
                article.llm_score = item.score
                article.llm_confidence = item.confidence
                article.category = item.category
                article.ranking_reason = item.reason
                selected.append(article)
                if len(selected) == limit:
                    break
            if response.items and not selected:
                raise ValueError("Gemini returned no known article IDs")
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
            result = self._client.interactions.create(
                model=self.model,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema.model_json_schema(),
                },
            )
        except Exception as exc:
            # The SDK exposes several transport-specific exceptions; the boundary
            # converts all of them to one treated, observable fallback signal.
            raise RuntimeError(f"Gemini request failed: {type(exc).__name__}") from exc
        output_text = getattr(result, "output_text", None)
        if not isinstance(output_text, str) or not output_text:
            raise RuntimeError("Gemini returned an empty response")
        return output_text


def _ranking_prompt(payload: list[dict[str, Any]], limit: int) -> str:
    return (
        "Ordena noticias sobre IA y hardware usando solamente los datos entregados. "
        f"Selecciona todos los candidatos relevantes, hasta {limit}. Si existen al menos "
        f"{limit} relevantes, devuelve exactamente {limit}; si existen menos, devuelve todos. "
        "No completes el cupo con candidatos irrelevantes. Devuelve JSON según el schema. "
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
