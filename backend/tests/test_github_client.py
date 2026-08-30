import json

import httpx
import pytest

from app.github.client import GitHubApiError, GitHubClient


def test_github_client_exchanges_token_lists_repositories_and_creates_webhook():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gho-token"})
        if request.url.path == "/user":
            assert request.headers["Authorization"] == "Bearer gho-token"
            return httpx.Response(200, json={"id": 42, "login": "octocat"})
        if request.url.path == "/user/repos":
            return httpx.Response(
                200,
                json=[{"id": 101, "full_name": "octocat/demo", "name": "demo", "private": False}],
            )
        if request.url.path == "/repos/octocat/demo/hooks":
            assert request.method == "POST"
            assert json.loads(request.content)["config"]["content_type"] == "json"
            return httpx.Response(201, json={"id": 7, "active": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = GitHubClient(
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(handler),
    )

    assert client.exchange_code("code") == "gho-token"
    assert client.get_identity("gho-token").login == "octocat"
    assert client.list_repositories("gho-token")[0].full_name == "octocat/demo"
    assert client.create_webhook("gho-token", "octocat/demo", "https://repoops.dev/hook", "secret").id == 7


def test_github_client_maps_forbidden_response_to_domain_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Resource not accessible"})

    client = GitHubClient(
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(GitHubApiError) as error:
        client.list_repositories("gho-token")

    assert error.value.status_code == 403
    assert "not accessible" in str(error.value)


def test_github_client_lists_quality_data_with_normalized_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octocat/demo/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 11,
                        "number": 3,
                        "title": "Improve docs",
                        "body": "Details",
                        "state": "open",
                        "user": {"login": "octocat"},
                        "head": {"ref": "docs", "sha": "abc"},
                        "base": {"ref": "main"},
                        "merged_at": "2026-08-26T08:00:00Z",
                        "html_url": "https://github.com/octocat/demo/pull/3",
                    }
                ],
            )
        if request.url.path == "/repos/octocat/demo/actions/runs":
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "id": 21,
                            "name": "CI",
                            "status": "completed",
                            "conclusion": "failure",
                            "head_branch": "main",
                            "head_sha": "def",
                            "html_url": "https://github.com/octocat/demo/actions/runs/21",
                        }
                    ]
                },
            )
        if request.url.path == "/repos/octocat/demo/releases":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 31,
                        "tag_name": "v1.0.0",
                        "name": "First release",
                        "body": "Notes",
                        "published_at": "2026-08-27T10:00:00Z",
                        "html_url": "https://github.com/octocat/demo/releases/tag/v1.0.0",
                    }
                ],
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = GitHubClient(
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(handler),
    )

    pull_request = client.list_pull_requests("gho-token", "octocat/demo")[0]
    workflow = client.list_workflow_runs("gho-token", "octocat/demo")[0]
    release = client.list_releases("gho-token", "octocat/demo")[0]

    assert pull_request.head_branch == "docs"
    assert pull_request.base_branch == "main"
    assert pull_request.merged_at == "2026-08-26T08:00:00Z"
    assert pull_request.author_login == "octocat"
    assert workflow.conclusion == "failure"
    assert release.published_at == "2026-08-27T10:00:00Z"
