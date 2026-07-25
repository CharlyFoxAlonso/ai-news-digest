import json
import subprocess
from datetime import UTC, date, datetime, timedelta

import pytest

from ai_news.models import HistoryEntry, RunKind, RunStatus
from ai_news.persistence.git_state import GitStateBranch, GitStateError
from ai_news.persistence.history import StateStore, atomic_write_json


def history_entry(day: date) -> HistoryEntry:
    return HistoryEntry(
        digest_date_local=day.isoformat(),
        canonical_urls=[f"https://example.com/{day}"],
        article_hashes=[day.isoformat()],
        titles=["Title"],
        smtp_accepted_at_utc=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
    )


def test_atomic_write_leaves_valid_json(tmp_path) -> None:
    path = tmp_path / "state.json"
    atomic_write_json(path, {"status": "sent"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "sent"}
    assert list(tmp_path.glob("*.tmp")) == []


def test_state_round_trip(tmp_path) -> None:
    store = StateStore(tmp_path)
    state = store.load_state(date(2026, 7, 25), RunKind.PRINCIPAL, "run")
    state.status = RunStatus.SENT
    store.save_state(state)
    assert store.load_state(date(2026, 7, 25), RunKind.PRINCIPAL, "new").status is RunStatus.SENT


def test_history_retains_30_days(tmp_path) -> None:
    store = StateStore(tmp_path)
    today = date(2026, 7, 30)
    for offset in range(35, -1, -1):
        store.append_history(history_entry(today - timedelta(days=offset)), today)
    history = store.load_history()
    assert len(history) == 30
    assert history[0].digest_date_local == (today - timedelta(days=29)).isoformat()


def completed(returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, "", stderr)


def test_git_branch_bootstrap_is_idempotent(tmp_path) -> None:
    commands = []
    responses = iter([completed(1), completed(0), completed(0), completed(0)])

    def runner(command, _cwd):
        commands.append(tuple(command))
        return next(responses)

    branch = GitStateBranch(tmp_path, runner=runner)
    assert branch.bootstrap()
    assert not branch.bootstrap()
    assert ("git", "switch", "--orphan", "digest-state") in commands


def test_non_fast_forward_rebases_and_retries(tmp_path) -> None:
    commands = []
    responses = iter([completed(1, "non-fast-forward"), completed(), completed(), completed()])

    def runner(command, _cwd):
        commands.append(tuple(command))
        return next(responses)

    GitStateBranch(tmp_path, runner=runner).push_with_rebase_retry()
    assert commands.count(("git", "push", "origin", "HEAD:digest-state")) == 2
    assert ("git", "rebase", "origin/digest-state") in commands


def test_push_conflict_eventually_fails(tmp_path) -> None:
    responses = iter([completed(1, "conflict"), completed(), completed(), completed(1, "conflict")])
    branch = GitStateBranch(tmp_path, runner=lambda _command, _cwd: next(responses))
    with pytest.raises(GitStateError, match="conflict"):
        branch.push_with_rebase_retry()
