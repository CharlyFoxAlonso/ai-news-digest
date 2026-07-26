import hashlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Protocol

import structlog

from ai_news.acquisition import FeedResult
from ai_news.dedup import deduplicate
from ai_news.email_builder import build_digest_email
from ai_news.filtering import filter_articles
from ai_news.llm.gemini import GeminiDigestService
from ai_news.models import (
    DailyRunState,
    DigestEntry,
    HistoryEntry,
    RunKind,
    RunStatus,
)
from ai_news.normalization import article_from_feed
from ai_news.persistence.history import StateStore
from ai_news.ranking import rank_heuristically
from ai_news.time_utils import digest_date, is_within_article_window

logger = structlog.get_logger()


class Delivery(Protocol):
    accepted: bool

    def send(self, message: EmailMessage) -> None: ...


class IssueReporter(Protocol):
    def report_once(self, digest_date: str, error_type: str, details: str) -> bool: ...


Acquire = Callable[[], Awaitable[list[FeedResult]]]


@dataclass(slots=True)
class RunOutcome:
    state: DailyRunState
    entries: list[DigestEntry]
    email_sent: bool
    skipped_reason: str | None = None


class DigestOrchestrator:
    def __init__(
        self,
        *,
        state_store: StateStore,
        acquire: Acquire,
        llm: GeminiDigestService,
        delivery: Delivery,
        sender: str,
        recipient: str,
        repository: str,
        issue_reporter: IssueReporter | None = None,
    ) -> None:
        self.state_store = state_store
        self.acquire = acquire
        self.llm = llm
        self.delivery = delivery
        self.sender = sender
        self.recipient = recipient
        self.repository = repository
        self.issue_reporter = issue_reporter

    async def run(
        self,
        run_kind: RunKind,
        *,
        dry_run: bool = False,
        now_utc: datetime | None = None,
    ) -> RunOutcome:
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        local_date = digest_date(now)
        run_id = str(uuid.uuid4())
        state = self.state_store.load_state(local_date, run_kind, run_id)
        reason = self._skip_reason(state, run_kind)
        if reason:
            if state.status in {RunStatus.SENDING, RunStatus.DELIVERY_UNCERTAIN}:
                self._report_review(state, reason)
            return RunOutcome(state=state, entries=[], email_sent=False, skipped_reason=reason)
        if not dry_run:
            state.status = RunStatus.STARTED
            state.run_kind = run_kind
            state.run_id = run_id
            state.started_at_utc = now
            state.finished_at_utc = None
            state.last_error = None
            self.state_store.save_state(state)
        try:
            results = await self.acquire()
            articles = [
                article
                for result in results
                for item in result.items
                if (article := article_from_feed(item)) is not None
            ]
            acquired_count = sum(len(result.items) for result in results)
            temporal = [
                article
                for article in articles
                if is_within_article_window(article.published_at_utc, now)
            ]
            current = filter_articles(articles, now)
            logger.info(
                "digest_articles_filtered",
                acquired_count=acquired_count,
                normalized_count=len(articles),
                temporal_count=len(temporal),
                temporal_discarded_count=len(articles) - len(temporal),
                filtered_count=len(current),
                thematic_discarded_count=len(temporal) - len(current),
            )
            unique = deduplicate(current)
            logger.info(
                "digest_articles_deduplicated",
                input_count=len(current),
                deduplicated_count=len(unique),
                duplicates_removed_count=len(current) - len(unique),
            )
            sent_urls = {
                url for history in self.state_store.load_history() for url in history.canonical_urls
            }
            unseen = [item for item in unique if str(item.url_canonical) not in sent_urls]
            ranked = rank_heuristically(unseen, now)
            logger.info(
                "llm_candidates_sent",
                candidate_count=len(ranked),
                candidate_article_ids=[article.article_id for article in ranked],
                history_excluded_count=len(unique) - len(unseen),
            )
            selected = self.llm.rank(ranked, limit=5)
            entries = [self.llm.summarize(article) for article in selected]
            logger.info(
                "digest_selection_completed",
                selected_article_ids=[article.article_id for article in selected],
                final_count=len(selected),
                dry_run=dry_run,
            )
            message = build_digest_email(
                entries,
                digest_date=local_date,
                sender=self.sender,
                recipient=self.recipient,
                repository=self.repository,
            )
            state.selected_articles = [article.article_id for article in selected]
            state.smtp_message_id = str(message["Message-ID"])
            if dry_run:
                return RunOutcome(state=state, entries=entries, email_sent=False)
            state.status = RunStatus.SENDING
            self.state_store.save_state(state)
            self.delivery.send(message)
            logger.info(
                "digest_email_sent",
                run_id=run_id,
                final_article_count=len(selected),
            )
            accepted_at = datetime.now(UTC)
            state.status = RunStatus.SENT
            state.finished_at_utc = accepted_at
            try:
                self.state_store.save_state(state)
            except OSError as exc:
                state.status = RunStatus.DELIVERY_UNCERTAIN
                state.last_error = f"state persistence failed after SMTP acceptance: {exc}"
                try:
                    self.state_store.save_state(state)
                except OSError:
                    logger.critical("delivery_uncertain_state_unpersisted", run_id=run_id)
                self._report_review(state, state.last_error)
                raise RuntimeError(state.last_error) from exc
            history_entry = HistoryEntry(
                digest_date_local=local_date.isoformat(),
                canonical_urls=[str(article.url_canonical) for article in selected],
                article_hashes=[
                    hashlib.sha256(str(article.url_canonical).encode()).hexdigest()
                    for article in selected
                ],
                titles=[article.title for article in selected],
                smtp_accepted_at_utc=accepted_at,
            )
            self.state_store.append_history(history_entry, local_date)
            logger.info("digest_run_finished", run_id=run_id, status=state.status)
            return RunOutcome(state=state, entries=entries, email_sent=True)
        except Exception as exc:
            # This is the orchestration boundary: every failure is recorded before
            # propagating, while accepted SMTP messages remain non-retryable.
            if not dry_run and state.status not in {RunStatus.SENT, RunStatus.DELIVERY_UNCERTAIN}:
                state.status = RunStatus.FAILED
                state.finished_at_utc = datetime.now(UTC)
                state.last_error = f"{type(exc).__name__}: {exc}"
                self.state_store.save_state(state)
            logger.error("digest_run_failed", run_id=run_id, error=f"{type(exc).__name__}: {exc}")
            raise

    @staticmethod
    def _skip_reason(state: DailyRunState, run_kind: RunKind) -> str | None:
        if state.status is RunStatus.SENT:
            return "digest already sent"
        if state.status is RunStatus.SENDING:
            return "SMTP outcome requires review; automatic resend disabled"
        if state.status is RunStatus.DELIVERY_UNCERTAIN:
            return "delivery is uncertain; automatic resend disabled"
        if run_kind is RunKind.RECOVERY and state.status in {
            RunStatus.NOT_STARTED,
            RunStatus.STARTED,
            RunStatus.FAILED,
        }:
            return None
        return None

    def _report_review(self, state: DailyRunState, details: str) -> None:
        if self.issue_reporter:
            self.issue_reporter.report_once(
                state.digest_date_local, state.status.value, details
            )
