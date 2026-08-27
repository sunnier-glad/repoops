from app.ci.service import list_failed_workflows
from app.db.models import Base, Repository, User, WorkflowRun
from app.db.session import create_database_engine, create_session_factory


def test_failed_workflow_query_is_scoped_to_current_users_repositories(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'ci.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        owner = User()
        other = User()
        session.add_all([owner, other])
        session.flush()
        own_repo = Repository(
            user_id=owner.id,
            github_id=1,
            owner="octocat",
            name="demo",
            full_name="octocat/demo",
            private=False,
            encrypted_webhook_secret="unused",
        )
        other_repo = Repository(
            user_id=other.id,
            github_id=2,
            owner="other",
            name="private",
            full_name="other/private",
            private=True,
            encrypted_webhook_secret="unused",
        )
        session.add_all([own_repo, other_repo])
        session.flush()
        session.add_all(
            [
                WorkflowRun(
                    repository_id=own_repo.id,
                    github_id=10,
                    workflow_name="CI",
                    status="completed",
                    conclusion="failure",
                    branch="main",
                    commit_sha="abc",
                ),
                WorkflowRun(
                    repository_id=other_repo.id,
                    github_id=20,
                    workflow_name="CI",
                    status="completed",
                    conclusion="failure",
                    branch="main",
                    commit_sha="def",
                ),
            ]
        )
        session.commit()

        failed = list_failed_workflows(session, owner.id)

    assert [item.github_id for item in failed] == [10]
