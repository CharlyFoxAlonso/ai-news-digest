from datetime import UTC, datetime

import pytest

from ai_news.acquisition import FeedResult
from ai_news.feed_parser import ParsedFeedItem
from ai_news.llm.gemini import GeminiDigestService
from ai_news.models import DailyRunState, RunKind, RunStatus
from ai_news.orchestrator import DigestOrchestrator
from ai_news.persistence.history import StateStore
from ai_news.sources.base import FeedSource


class FakeDelivery:
    def __init__(self, fail: bool = False) -> None:
        self.accepted = False
        self.calls = 0
        self.fail = fail

    def send(self, _message) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("SMTP rejected")
        self.accepted = True


class FakeReporter:
    def __init__(self) -> None:
        self.calls = 0

    def report_once(self, *_args) -> bool:
        self.calls += 1
        return True


def llm() -> GeminiDigestService:
    return GeminiDigestService("x", "model", responder=lambda _prompt, _schema: "{")


def feed_result() -> FeedResult:
    source = FeedSource("OpenAI", "https://example.com/feed", 100)
    item = ParsedFeedItem(
        source=source,
        title="New GPU model improves AI inference",
        url="https://example.com/article",
        description="A machine learning inference release.",
        category="AI",
        published_at_utc=datetime(2026, 7, 25, 11, tzinfo=UTC),
    )
    return FeedResult(source=source, items=[item])


def orchestrator(tmp_path, delivery, results=None, reporter=None):
    async def acquire():
        return [feed_result()] if results is None else results

    return DigestOrchestrator(
        state_store=StateStore(tmp_path),
        acquire=acquire,
        llm=llm(),
        delivery=delivery,
        sender="sender@example.com",
        recipient="reader@example.com",
        repository="owner/repo",
        issue_reporter=reporter,
    )


@pytest.mark.asyncio
async def test_principal_sends_and_persists_history(tmp_path) -> None:
    delivery = FakeDelivery()
    outcome = await orchestrator(tmp_path, delivery).run(
        RunKind.PRINCIPAL, now_utc=datetime(2026, 7, 25, 12, tzinfo=UTC)
    )
    assert outcome.state.status is RunStatus.SENT
    assert delivery.calls == 1
    assert len(StateStore(tmp_path).load_history()) == 1


@pytest.mark.asyncio
async def test_sent_state_is_noop_for_recovery(tmp_path) -> None:
    store = StateStore(tmp_path)
    store.save_state(
        DailyRunState(
            digest_date_local="2026-07-25",
            status=RunStatus.SENT,
            run_kind=RunKind.PRINCIPAL,
            run_id="old",
        )
    )
    delivery = FakeDelivery()
    outcome = await orchestrator(tmp_path, delivery).run(
        RunKind.RECOVERY, now_utc=datetime(2026, 7, 25, 12, tzinfo=UTC)
    )
    assert outcome.skipped_reason
    assert delivery.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [RunStatus.SENDING, RunStatus.DELIVERY_UNCERTAIN])
async def test_uncertain_recovery_does_not_resend_and_reports(tmp_path, status) -> None:
    store = StateStore(tmp_path)
    store.save_state(
        DailyRunState(
            digest_date_local="2026-07-25",
            status=status,
            run_kind=RunKind.PRINCIPAL,
            run_id="old",
        )
    )
    delivery = FakeDelivery()
    reporter = FakeReporter()
    await orchestrator(tmp_path, delivery, reporter=reporter).run(
        RunKind.RECOVERY, now_utc=datetime(2026, 7, 25, 12, tzinfo=UTC)
    )
    assert delivery.calls == 0
    assert reporter.calls == 1


@pytest.mark.asyncio
async def test_failed_recovery_retries_and_empty_digest_sends(tmp_path) -> None:
    StateStore(tmp_path).save_state(
        DailyRunState(
            digest_date_local="2026-07-25",
            status=RunStatus.FAILED,
            run_kind=RunKind.PRINCIPAL,
            run_id="old",
        )
    )
    delivery = FakeDelivery()
    outcome = await orchestrator(tmp_path, delivery, results=[]).run(
        RunKind.RECOVERY, now_utc=datetime(2026, 7, 25, 12, tzinfo=UTC)
    )
    assert outcome.state.status is RunStatus.SENT
    assert outcome.entries == []


@pytest.mark.asyncio
async def test_dry_run_never_invokes_smtp(tmp_path) -> None:
    delivery = FakeDelivery()
    outcome = await orchestrator(tmp_path, delivery).run(
        RunKind.MANUAL, dry_run=True, now_utc=datetime(2026, 7, 25, 12, tzinfo=UTC)
    )
    assert not outcome.email_sent
    assert delivery.calls == 0
    assert not (tmp_path / "state.json").exists()
