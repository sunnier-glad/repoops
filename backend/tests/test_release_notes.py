from datetime import UTC, datetime

from app.db.models import Base, PullRequest, Release, Repository, User
from app.db.session import create_database_engine, create_session_factory
from app.releases.service import (
    generate_release_note_draft,
    get_release_note_draft,
    release_note_draft_payload,
    update_release_note_draft,
)


def make_repository(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'notes.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    session = factory()
    user = User()
    session.add(user)
    session.flush()
    repository = Repository(
        user_id=user.id,
        github_id=101,
        owner="octocat",
        name="notes",
        full_name="octocat/notes",
        default_branch="main",
        private=False,
        encrypted_webhook_secret="unused",
    )
    session.add(repository)
    session.commit()
    return session, repository


def test_release_note_draft_uses_only_newly_merged_default_branch_prs(tmp_path):
    session, repository = make_repository(tmp_path)
    release = Release(
        repository_id=repository.id,
        github_id=30,
        tag_name="v1.0.0",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    session.add(release)
    session.flush()
    session.add_all(
        [
            _pull_request(repository.id, 1, "Old change", "main", datetime(2026, 7, 31, tzinfo=UTC)),
            _pull_request(repository.id, 2, "New feature", "main", datetime(2026, 8, 10, tzinfo=UTC)),
            _pull_request(repository.id, 3, "Development only", "develop", datetime(2026, 8, 11, tzinfo=UTC)),
            _pull_request(repository.id, 4, "Still open", "main", None),
        ]
    )
    session.commit()

    draft = generate_release_note_draft(session, repository, "v1.1.0")
    payload = release_note_draft_payload(session, draft)

    assert draft.source_pr_count == 1
    assert "New feature" in draft.content
    assert "Old change" not in draft.content
    assert "Development only" not in draft.content
    assert payload["based_on_release"]["tag_name"] == "v1.0.0"
    assert payload["sources"][0]["number"] == 2
    session.close()


def test_release_note_draft_can_be_regenerated_and_edited(tmp_path):
    session, repository = make_repository(tmp_path)

    first = generate_release_note_draft(session, repository, "v0.1.0")
    second = generate_release_note_draft(session, repository, "v0.2.0")
    edited = update_release_note_draft(session, repository, "# v0.2.0\n\nEdited\n")

    assert first.id == second.id == edited.id
    assert edited.version == "v0.2.0"
    assert get_release_note_draft(session, repository).content.endswith("Edited\n")
    session.close()


def _pull_request(
    repository_id: int,
    number: int,
    title: str,
    base_branch: str,
    merged_at: datetime | None,
) -> PullRequest:
    return PullRequest(
        repository_id=repository_id,
        github_id=number,
        number=number,
        title=title,
        state="closed" if merged_at else "open",
        head_branch=f"feature/{number}",
        base_branch=base_branch,
        author_login="octocat",
        html_url=f"https://example.test/pull/{number}",
        merged_at=merged_at,
    )
