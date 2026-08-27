from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.dependencies import get_current_user
from app.ci.service import list_failed_workflows
from app.db.models import PullRequest, Release, Repository
from app.github.client import GitHubApiError
from app.github.service import bind_repository, list_available_repositories


class BindRepositoryRequest(BaseModel):
    full_name: str


router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.get("/available")
def available_repositories(request: Request) -> list[dict[str, object]]:
    user = get_current_user(request)
    repositories = list_available_repositories(
        user, request.app.state.github_client, request.app.state.token_cipher
    )
    return [
        {"full_name": item.full_name, "name": item.name, "private": item.private}
        for item in repositories
    ]


@router.post("", status_code=201)
def create_repository(request: Request, body: BindRepositoryRequest) -> dict[str, object]:
    user = get_current_user(request)
    try:
        with request.app.state.session_factory() as session:
            repository = bind_repository(
                session,
                user,
                body.full_name,
                request.app.state.github_client,
                request.app.state.token_cipher,
                request.app.state.settings.github_webhook_base_url,
            )
            return {
                "id": repository.id,
                "full_name": repository.full_name,
                "private": repository.private,
                "webhook_configured": repository.github_webhook_id is not None,
            }
    except GitHubApiError as exc:
        status_code = exc.status_code if exc.status_code in {403, 404, 429} else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{repository_id}/pull-requests")
def pull_requests(request: Request, repository_id: int) -> list[dict[str, object]]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        _require_owned_repository(session, repository_id, user.id)
        items = session.scalars(
            select(PullRequest)
            .where(PullRequest.repository_id == repository_id)
            .order_by(PullRequest.updated_at.desc())
        )
        return [
            {
                "number": item.number,
                "title": item.title,
                "state": item.state,
                "head_branch": item.head_branch,
                "head_sha": item.head_sha,
                "html_url": item.html_url,
            }
            for item in items
        ]


@router.get("/{repository_id}/ci/failures")
def failed_workflows(request: Request, repository_id: int) -> list[dict[str, object]]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        _require_owned_repository(session, repository_id, user.id)
        items = list_failed_workflows(session, user.id)
        return [
            {
                "id": item.id,
                "workflow_name": item.workflow_name,
                "branch": item.branch,
                "commit_sha": item.commit_sha,
                "conclusion": item.conclusion,
                "html_url": item.html_url,
            }
            for item in items
            if item.repository_id == repository_id
        ]


@router.get("/{repository_id}/releases")
def releases(request: Request, repository_id: int) -> list[dict[str, object]]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        _require_owned_repository(session, repository_id, user.id)
        items = session.scalars(
            select(Release)
            .where(Release.repository_id == repository_id)
            .order_by(Release.updated_at.desc())
        )
        return [
            {
                "id": item.id,
                "tag_name": item.tag_name,
                "name": item.name,
                "body": item.body,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "html_url": item.html_url,
            }
            for item in items
        ]


def _require_owned_repository(session, repository_id: int, user_id: int) -> Repository:
    repository = session.scalar(
        select(Repository).where(Repository.id == repository_id, Repository.user_id == user_id)
    )
    if repository is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return repository
