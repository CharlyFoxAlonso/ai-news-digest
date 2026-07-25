import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

CommandRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )


class GitStateError(RuntimeError):
    pass


class GitStateBranch:
    """Manage the dedicated state branch in an isolated checkout or worktree."""

    def __init__(
        self,
        repository: Path,
        *,
        branch: str = "digest-state",
        remote: str = "origin",
        runner: CommandRunner = _run,
    ) -> None:
        self.repository = repository
        self.branch = branch
        self.remote = remote
        self.runner = runner

    def bootstrap(self) -> bool:
        exists = self.runner(
            ("git", "show-ref", "--verify", "--quiet", f"refs/heads/{self.branch}"),
            self.repository,
        )
        if exists.returncode == 0:
            self._checked(("git", "switch", self.branch))
            return False
        self._checked(("git", "switch", "--orphan", self.branch))
        return True

    def commit_if_changed(self, message: str) -> bool:
        self._checked(("git", "add", "state.json", "history.json"))
        diff = self.runner(("git", "diff", "--cached", "--quiet"), self.repository)
        if diff.returncode == 0:
            return False
        if diff.returncode != 1:
            raise GitStateError(diff.stderr.strip() or "unable to inspect staged state")
        self._checked(("git", "commit", "-m", message))
        return True

    def push_with_rebase_retry(self, attempts: int = 2) -> None:
        for attempt in range(attempts):
            pushed = self.runner(
                ("git", "push", self.remote, f"HEAD:{self.branch}"), self.repository
            )
            if pushed.returncode == 0:
                return
            if attempt + 1 < attempts:
                self._checked(("git", "fetch", self.remote, self.branch))
                self._checked(("git", "rebase", f"{self.remote}/{self.branch}"))
        raise GitStateError(pushed.stderr.strip() or "state push failed after retry")

    def _checked(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        result = self.runner(command, self.repository)
        if result.returncode != 0:
            raise GitStateError(result.stderr.strip() or f"command failed: {' '.join(command)}")
        return result
