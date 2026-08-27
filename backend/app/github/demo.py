from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import PullRequest, Release, Repository, WorkflowRun


def load_demo_data(session: Session, repository: Repository) -> dict[str, int | bool]:
    clear_demo_data(session, repository, commit=False)
    session.add(
        PullRequest(
            repository_id=repository.id,
            github_id=-999001,
            number=999001,
            title="演示：为发布流程增加回归检查",
            body="这是一条本地演示 PR，不代表 GitHub 真实数据。",
            state="open",
            head_branch="demo/release-quality",
            head_sha="demo-pr-sha",
            author_login="repoops-demo",
            html_url="https://example.test/repoops/demo-pr",
            is_demo=True,
        )
    )
    session.add(
        WorkflowRun(
            repository_id=repository.id,
            github_id=-999002,
            workflow_name="演示 CI · 回归检查",
            status="completed",
            conclusion="failure",
            branch="demo/release-quality",
            commit_sha="demo-ci-sha",
            html_url="https://example.test/repoops/demo-ci",
            is_demo=True,
        )
    )
    session.add(
        Release(
            repository_id=repository.id,
            github_id=-999003,
            tag_name="demo-v1.0.0",
            name="演示 Release · 首次质量检查",
            body="这是一条本地演示 Release。",
            published_at=datetime.now(UTC),
            html_url="https://example.test/repoops/demo-release",
            is_demo=True,
        )
    )
    session.commit()
    return {"demo": True, "pull_requests": 1, "failed_workflows": 1, "releases": 1}


def clear_demo_data(
    session: Session, repository: Repository, *, commit: bool = True
) -> int:
    deleted = 0
    for model in (PullRequest, WorkflowRun, Release):
        result = session.execute(
            delete(model).where(model.repository_id == repository.id, model.is_demo.is_(True))
        )
        deleted += result.rowcount or 0
    if commit:
        session.commit()
    return deleted
