import hashlib
import hmac
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth.service import GitHubIdentity
from app.config import Settings
from app.db.models import (
    Job,
    PullRequest,
    Release,
    ReleaseChecklist,
    Repository,
    User,
    WorkflowRun,
)
from app.github.schemas import GitHubRepository, WebhookInfo
from app.main import create_app


class FakeGitHubClient:
    def __init__(self):
        self.last_webhook_secret = ""

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

    def list_pull_requests(self, access_token: str, repository: str):
        return [SimpleNamespace(github_id=11, number=3, title="Improve docs", body="Details", state="open", head_branch="docs", base_branch="main", head_sha="abc", author_login="octocat", html_url="https://example.test/pr/3", merged_at=None)]

    def list_workflow_runs(self, access_token: str, repository: str):
        return [SimpleNamespace(github_id=21, workflow_name="CI", status="completed", conclusion="failure", branch="main", commit_sha="def", html_url="https://example.test/run/21")]

    def list_releases(self, access_token: str, repository: str):
        return [SimpleNamespace(github_id=31, tag_name="v1.0.0", name="First release", body="Notes", published_at="2026-08-27T10:00:00Z", html_url="https://example.test/release/31")]


def make_client(tmp_path, webhook_enabled=True):
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'repoops.db'}",
        github_client_id="client-id",
        github_client_secret="client-secret",
        github_redirect_uri="http://testserver/api/auth/github/callback",
        github_webhook_base_url="https://repoops.example.com",
        github_webhook_enabled=webhook_enabled,
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


def test_local_mode_binds_repository_without_registering_webhook(tmp_path):
    client = make_client(tmp_path, webhook_enabled=False)
    login(client)

    bound = client.post("/api/repositories", json={"full_name": "octocat/demo"})

    assert bound.status_code == 201
    assert bound.json() == {
        "id": 1,
        "full_name": "octocat/demo",
        "private": False,
        "webhook_configured": False,
    }
    assert client.fake_github.last_webhook_secret == ""


def test_bound_repositories_can_be_restored_after_page_refresh(tmp_path):
    client = make_client(tmp_path, webhook_enabled=False)
    login(client)
    client.post("/api/repositories", json={"full_name": "octocat/demo"})

    response = client.get("/api/repositories")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "full_name": "octocat/demo",
            "private": False,
            "webhook_configured": False,
        }
    ]


def test_sync_endpoint_imports_current_github_quality_data(tmp_path):
    client = make_client(tmp_path, webhook_enabled=False)
    login(client)
    repository = client.post("/api/repositories", json={"full_name": "octocat/demo"}).json()

    response = client.post(f"/api/repositories/{repository['id']}/sync")

    assert response.status_code == 200
    assert response.json() == {"pull_requests": 1, "failed_workflows": 1, "releases": 1}
    assert client.get(f"/api/repositories/{repository['id']}/pull-requests").json()[0]["number"] == 3
    assert client.get(f"/api/repositories/{repository['id']}/ci/failures").json()[0]["workflow_name"] == "CI"
    assert client.get(f"/api/repositories/{repository['id']}/releases").json()[0]["tag_name"] == "v1.0.0"
    assert "is_demo" not in client.get(f"/api/repositories/{repository['id']}/pull-requests").json()[0]
    quality_gate = client.get(f"/api/repositories/{repository['id']}/quality-gate")
    assert quality_gate.status_code == 200
    assert quality_gate.json()["status"] == "blocked"
    assert [item["key"] for item in quality_gate.json()["checks"]] == [
        "default_branch_ci",
        "open_pull_requests",
        "release_notes",
    ]
    generated_draft = client.post(
        f"/api/repositories/{repository['id']}/release-notes/draft",
        json={"version": "v1.1.0"},
    )
    assert generated_draft.status_code == 200
    assert generated_draft.json()["version"] == "v1.1.0"
    assert generated_draft.json()["source_pr_count"] == 0
    saved_draft = client.put(
        f"/api/repositories/{repository['id']}/release-notes/draft",
        json={"content": "# v1.1.0\n\nEdited notes\n"},
    )
    assert saved_draft.status_code == 200
    assert saved_draft.json()["content"].endswith("Edited notes\n")
    assert client.get(
        f"/api/repositories/{repository['id']}/release-notes/draft"
    ).json()["content"].endswith("Edited notes\n")

    with client.repoops_app.state.session_factory() as session:
        assert session.query(PullRequest).count() == 1
        assert session.query(WorkflowRun).count() == 1
        assert session.query(Release).count() == 1


def test_release_readiness_persists_manual_checks_without_overriding_gate(tmp_path):
    client = make_client(tmp_path, webhook_enabled=False)
    login(client)
    repository = client.post(
        "/api/repositories", json={"full_name": "octocat/demo"}
    ).json()
    client.post(f"/api/repositories/{repository['id']}/sync")

    missing_draft = client.put(
        f"/api/repositories/{repository['id']}/release-readiness",
        json={
            "change_scope_confirmed": True,
            "rollback_plan_confirmed": True,
            "release_window_confirmed": True,
        },
    )
    assert missing_draft.status_code == 409

    client.post(
        f"/api/repositories/{repository['id']}/release-notes/draft",
        json={"version": "v1.1.0"},
    )
    saved = client.put(
        f"/api/repositories/{repository['id']}/release-readiness",
        json={
            "change_scope_confirmed": True,
            "rollback_plan_confirmed": True,
            "release_window_confirmed": True,
        },
    )

    assert saved.status_code == 200
    assert saved.json()["status"] == "blocked"
    assert saved.json()["ready_to_release"] is False
    assert saved.json()["updated_by"] == "octocat"
    assert all(item["confirmed"] for item in saved.json()["manual_checks"])

    with client.repoops_app.state.session_factory() as session:
        workflow = session.query(WorkflowRun).one()
        workflow.conclusion = "success"
        pull_request = session.query(PullRequest).one()
        pull_request.state = "closed"
        session.commit()
        assert session.query(ReleaseChecklist).count() == 1

    ready = client.get(
        f"/api/repositories/{repository['id']}/release-readiness"
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["ready_to_release"] is True
    assert ready.json()["progress"] == {"completed": 6, "total": 6}

    client.post(
        f"/api/repositories/{repository['id']}/release-notes/draft",
        json={"version": "v1.2.0"},
    )
    reset = client.get(
        f"/api/repositories/{repository['id']}/release-readiness"
    ).json()
    assert reset["version"] == "v1.2.0"
    assert reset["status"] == "pending"
    assert reset["updated_by"] is None
    assert not any(item["confirmed"] for item in reset["manual_checks"])


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
