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
