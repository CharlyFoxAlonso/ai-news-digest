import argparse
import asyncio
import os
from pathlib import Path

from ai_news.acquisition import acquire_feeds
from ai_news.config import Settings
from ai_news.delivery.smtp import GmailSMTPDelivery
from ai_news.issues import GitHubIssueReporter
from ai_news.llm.gemini import GeminiDigestService
from ai_news.logging_setup import configure_logging
from ai_news.models import RunKind
from ai_news.orchestrator import DigestOrchestrator
from ai_news.persistence.history import StateStore, atomic_write_json
from ai_news.sources.feed_list import FEED_SOURCES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and send the AI News Digest")
    parser.add_argument("--run-kind", choices=[item.value for item in RunKind], default="manual")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    configure_logging()
    settings = Settings(dry_run=args.dry_run)
    settings.require_delivery_secrets()
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
    smtp_password = (
        settings.smtp_app_password.get_secret_value() if settings.smtp_app_password else ""
    )
    llm = GeminiDigestService(api_key, settings.llm_model)
    delivery = GmailSMTPDelivery(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or "",
        app_password=smtp_password,
    )

    async def acquire() -> list:
        return await acquire_feeds(
            FEED_SOURCES,
            timeout_seconds=settings.feed_timeout_seconds,
            max_bytes=settings.max_feed_bytes,
            max_entries=settings.max_entries_per_feed,
        )

    token = os.getenv("GITHUB_TOKEN")
    reporter = GitHubIssueReporter(settings.repository, token) if token else None
    orchestrator = DigestOrchestrator(
        state_store=StateStore(settings.state_dir),
        acquire=acquire,
        llm=llm,
        delivery=delivery,
        sender=settings.smtp_username or "dry-run@example.invalid",
        recipient=str(settings.recipient_email),
        repository=settings.repository,
        issue_reporter=reporter,
    )
    try:
        outcome = await orchestrator.run(RunKind(args.run_kind), dry_run=settings.dry_run)
        report = {
            "status": outcome.state.status,
            "email_sent": outcome.email_sent,
            "selected_count": len(outcome.entries),
            "skipped_reason": outcome.skipped_reason,
        }
        artifacts = Path("artifacts")
        atomic_write_json(artifacts / "run-report.json", report)
        return 0
    finally:
        if reporter:
            reporter.close()


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
