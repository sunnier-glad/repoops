import hashlib
import hmac

from fastapi.testclient import TestClient

from app.auth.service import GitHubIdentity
from app.config import Settings
from app.db.models import Job, Repository, User
from app.github.schemas import GitHubRepository, WebhookInfo
from app.main import create_app


class FakeGitHubClient:
    last_webhook_secret = ""

    def exchange_code(self, code: str) -> str:
        return "raw-token"

    def get_identity(self, access_token: str) -> GitHubIdentity:
        return GitHubIdentity(42, "octocat", "The Octocat", None, access_token)

    def list_repositories(self, access_token: str) -> list[GitHubRepository]:
        return [GitHubRepository(101, "octocat/demo", "demo", False)]

    def create_webhook(
        self, access_token: str, repository: str, callback_url: str, secret: str
    ) -> WebhookInfo:
        self.last_webhook_secret = secret
        return WebhookInfo(7, True)


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'repoops.db'}",
        github_client_id="client-id",
        github_client_secret="client-secret",
        github_redirect_uri="http://testserver/api/auth/github/callback",
        github_webhook_base_url="https://repoops.example.com",
        session_secret="test-session-secret",
    )
    fake = FakeGitHubClient()
    app = create_app(settings=settings, github_client=fake)
    client = TestClient(app)
    client.fake_github = fake
    client.repoops_app = app
    return client


def login(client: TestClient) -> None:
    location = client.get("/api/auth/github", follow_redirects=False).headers["location"]
    state = location.split("state=", 1)[1]
    client.get(
        "/api/auth/github/callback",
        params={"code": "github-code", "state": state},
        follow_redirects=False,
    )


def test_repository_binding_only_allows_a_repository_from_github_account(tmp_path):
    client = make_client(tmp_path)
    login(client)

    available = client.get("/api/repositories/available")
    assert available.status_code == 200
    assert available.json() == [{"full_name": "octocat/demo", "name": "demo", "private": False}]

    bound = client.post("/api/repositories", json={"full_name": "octocat/demo"})
    assert bound.status_code == 201
    assert bound.json()["full_name"] == "octocat/demo"
    assert "webhook_secret" not in bound.json()

    rejected = client.post("/api/repositories", json={"full_name": "octocat/other"})
    assert rejected.status_code == 403


def test_webhook_verifies_signature_persists_raw_event_and_returns_202(tmp_path):
    client = make_client(tmp_path)
    login(client)
    repository = client.post("/api/repositories", json={"full_name": "octocat/demo"}).json()
    payload = b'{"action":"opened","number":1}'
    secret = client.fake_github.last_webhook_secret

    response = client.post(
        f"/api/webhooks/github/{repository['id']}",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Delivery": "delivery-1",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256="
            + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest(),
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "duplicate": False}
    with client.repoops_app.state.session_factory() as session:
        assert session.query(Job).filter_by(event_id=1, kind="process_webhook_event").count() == 1

    duplicate = client.post(
        f"/api/webhooks/github/{repository['id']}",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Delivery": "delivery-1",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256="
            + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest(),
        },
    )
    assert duplicate.status_code == 202
    assert duplicate.json() == {"status": "accepted", "duplicate": True}


def test_quality_api_hides_a_repository_owned_by_another_user(tmp_path):
    client = make_client(tmp_path)
    login(client)
    with client.repoops_app.state.session_factory() as session:
        other_user = User()
        session.add(other_user)
        session.flush()
        other_repository = Repository(
            user_id=other_user.id,
            github_id=999,
            owner="other",
            name="private",
            full_name="other/private",
            private=True,
            encrypted_webhook_secret="unused",
        )
        session.add(other_repository)
        session.commit()
        other_repository_id = other_repository.id

    response = client.get(f"/api/repositories/{other_repository_id}/pull-requests")
    assert response.status_code == 404
