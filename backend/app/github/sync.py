from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import TokenCipher
from app.db.models import PullRequest, Release, Repository, User, WorkflowRun
from app.github.client import GitHubClient
from app.github.service import github_access_token


def sync_repository_data(
    session: Session,
    user: User,
    repository: Repository,
    github: GitHubClient,
    cipher: TokenCipher,
) -> dict[str, int]:
    access_token = github_access_token(user, cipher)
    pull_requests = github.list_pull_requests(access_token, repository.full_name)
    workflow_runs = github.list_workflow_runs(access_token, repository.full_name)
    releases = github.list_releases(access_token, repository.full_name)

    for item in pull_requests:
        current = session.scalar(
            select(PullRequest).where(
                PullRequest.repository_id == repository.id,
                PullRequest.number == item.number,
            )
        )
        if current is None:
            current = PullRequest(repository_id=repository.id, number=item.number)
            session.add(current)
        current.github_id = item.github_id
        current.title = item.title
        current.body = item.body
        current.state = item.state
        current.head_branch = item.head_branch
        current.head_sha = item.head_sha
        current.author_login = item.author_login
        current.html_url = item.html_url
        current.is_demo = False

    for item in workflow_runs:
        current = session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.repository_id == repository.id,
                WorkflowRun.github_id == item.github_id,
            )
        )
        if current is None:
            current = WorkflowRun(repository_id=repository.id, github_id=item.github_id)
            session.add(current)
        current.workflow_name = item.workflow_name
        current.status = item.status
        current.conclusion = item.conclusion
        current.branch = item.branch
        current.commit_sha = item.commit_sha
        current.html_url = item.html_url
        current.is_demo = False

    for item in releases:
        current = session.scalar(
            select(Release).where(
                Release.repository_id == repository.id,
                Release.github_id == item.github_id,
            )
        )
        if current is None:
            current = Release(repository_id=repository.id, github_id=item.github_id)
            session.add(current)
        current.tag_name = item.tag_name
        current.name = item.name
        current.body = item.body
        current.published_at = _parse_github_datetime(item.published_at)
        current.html_url = item.html_url
        current.is_demo = False

    session.commit()
    return {
        "pull_requests": len(pull_requests),
        "failed_workflows": sum(item.conclusion == "failure" for item in workflow_runs),
        "releases": len(releases),
    }


def _parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
