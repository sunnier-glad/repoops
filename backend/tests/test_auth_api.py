from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.auth.service import GitHubIdentity
from app.config import Settings
from app.main import create_app


class FakeGitHubOAuthClient:
    def exchange_code(self, code: str) -> str:
        assert code == "github-code"
        return "raw-token"

    def get_identity(self, access_token: str) -> GitHubIdentity:
        assert access_token == "raw-token"
        return GitHubIdentity(
            github_user_id=42,
            login="octocat",
            name="The Octocat",
            avatar_url="https://github.com/octocat.png",
            access_token=access_token,
        )


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'repoops.db'}",
        github_client_id="client-id",
        github_redirect_uri="http://testserver/api/auth/github/callback",
        session_secret="test-session-secret",
    )
    return TestClient(create_app(settings=settings, github_client=FakeGitHubOAuthClient()))


def test_github_login_redirects_to_authorize_url(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/auth/github", follow_redirects=False)

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["client_id"] == ["client-id"]
    assert query["state"][0]


def test_github_callback_creates_session_and_current_user(tmp_path):
    client = make_client(tmp_path)
    login = client.get("/api/auth/github", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]

    callback = client.get(
        "/api/auth/github/callback",
        params={"code": "github-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/"
    current_user = client.get("/api/auth/me")
    assert current_user.status_code == 200
    assert current_user.json()["github_login"] == "octocat"
