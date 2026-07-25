import hashlib

import httpx
import structlog

logger = structlog.get_logger()


class GitHubIssueReporter:
    def __init__(self, repository: str, token: str, client: httpx.Client | None = None) -> None:
        self.repository = repository
        self.token = token
        self.client = client or httpx.Client(timeout=15)
        self._owns_client = client is None

    def report_once(self, digest_date: str, error_type: str, details: str) -> bool:
        fingerprint = hashlib.sha256(f"{digest_date}|{error_type}".encode()).hexdigest()[:12]
        marker = f"<!-- ai-news-digest:{fingerprint} -->"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        base = f"https://api.github.com/repos/{self.repository}/issues"
        try:
            existing = self.client.get(
                base,
                headers=headers,
                params={"state": "open", "labels": "automation-failure", "per_page": 100},
            )
            existing.raise_for_status()
            if any(marker in str(issue.get("body", "")) for issue in existing.json()):
                return False
            created = self.client.post(
                base,
                headers=headers,
                json={
                    "title": f"[automation] {error_type} — {digest_date}",
                    "body": f"{marker}\n\n{details[:2000]}",
                    "labels": ["automation-failure"],
                },
            )
            created.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("issue_report_failed", error=f"{type(exc).__name__}: {exc}")
            return False

    def close(self) -> None:
        if self._owns_client:
            self.client.close()
