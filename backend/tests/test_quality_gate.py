from app.db.models import Base, PullRequest, Release, Repository, User, WorkflowRun
from app.db.session import create_database_engine, create_session_factory
from app.quality.service import evaluate_release_quality


def make_repository(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'quality.db'}")
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
        name="demo",
        full_name="octocat/demo",
        default_branch="main",
        private=False,
        encrypted_webhook_secret="unused",
    )
    session.add(repository)
    session.commit()
    return session, repository


def test_quality_gate_blocks_when_latest_default_branch_ci_failed(tmp_path):
    session, repository = make_repository(tmp_path)
    session.add_all(
        [
            WorkflowRun(
                repository_id=repository.id,
                github_id=10,
                workflow_name="CI",
                status="completed",
                conclusion="success",
                branch="main",
                commit_sha="abc",
            ),
            WorkflowRun(
                repository_id=repository.id,
                github_id=20,
                workflow_name="CI",
                status="completed",
                conclusion="failure",
                branch="main",
                commit_sha="def",
                html_url="https://example.test/run/20",
            ),
        ]
    )
    session.commit()

    gate = evaluate_release_quality(session, repository)

    assert gate.status == "blocked"
    assert gate.checks[0].status == "fail"
    assert gate.checks[0].url == "https://example.test/run/20"
    session.close()


def test_quality_gate_warns_when_evidence_is_incomplete(tmp_path):
    session, repository = make_repository(tmp_path)
    session.add(
        PullRequest(
            repository_id=repository.id,
            github_id=11,
            number=3,
            title="Improve docs",
            state="open",
        )
    )
    session.commit()

    gate = evaluate_release_quality(session, repository)

    assert gate.status == "warning"
    assert [check.status for check in gate.checks] == ["warning", "warning", "warning"]
    session.close()


def test_quality_gate_is_ready_when_all_checks_pass(tmp_path):
    session, repository = make_repository(tmp_path)
    session.add_all(
        [
            WorkflowRun(
                repository_id=repository.id,
                github_id=20,
                workflow_name="CI",
                status="completed",
                conclusion="success",
                branch="main",
                commit_sha="def",
            ),
            Release(
                repository_id=repository.id,
                github_id=30,
                tag_name="v1.0.0",
                body="Initial release notes",
            ),
        ]
    )
    session.commit()

    gate = evaluate_release_quality(session, repository)

    assert gate.status == "ready"
    assert all(check.status == "pass" for check in gate.checks)
    session.close()
