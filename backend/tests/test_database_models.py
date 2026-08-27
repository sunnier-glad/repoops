from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, GitHubAccount, User


def test_user_and_github_account_persist_with_unique_github_identity():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User()
        session.add(user)
        session.flush()
        session.add(
            GitHubAccount(
                user_id=user.id,
                github_user_id=42,
                login="octocat",
                encrypted_access_token="encrypted-token",
            )
        )
        user_id = user.id
        session.commit()

        account = session.scalar(select(GitHubAccount).where(GitHubAccount.github_user_id == 42))

    assert account is not None
    assert account.login == "octocat"
    assert account.user_id == user_id
