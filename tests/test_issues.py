import hashlib

import httpx

from ai_news.issues import GitHubIssueReporter


def test_issue_is_not_duplicated() -> None:
    created_requests = []

    def create_handler(request: httpx.Request) -> httpx.Response:
        created_requests.append(request)
        return httpx.Response(200, json=[] if request.method == "GET" else {"number": 1})

    with httpx.Client(transport=httpx.MockTransport(create_handler)) as client:
        reporter = GitHubIssueReporter("owner/repo", "token", client)
        assert reporter.report_once("2026-07-25", "sending", "details")
        assert len(created_requests) == 2

    marker = hashlib.sha256(b"2026-07-25|sending").hexdigest()[:12]

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json=[{"body": f"<!-- ai-news-digest:{marker} -->"}]
            )
        )
    ) as client:
        reporter = GitHubIssueReporter("owner/repo", "token", client)
        assert not reporter.report_once("2026-07-25", "sending", "details")
