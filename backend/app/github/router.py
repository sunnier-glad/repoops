from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.dependencies import get_current_user
from app.ci.service import list_failed_workflows
from app.db.models import PullRequest, Release, Repository
from app.github.client import GitHubApiError
from app.github.service import bind_repository, list_available_repositories
from app.github.sync import sync_repository_data
from app.quality.service import evaluate_release_quality
from app.releases.readiness import (
    release_readiness_payload,
    update_release_checklist,
)
from app.releases.service import (
    generate_release_note_draft,
    get_release_note_draft,
    release_note_draft_payload,
    update_release_note_draft,
)


class BindRepositoryRequest(BaseModel):
    full_name: str


class GenerateReleaseNoteDraftRequest(BaseModel):
    version: str = Field(min_length=1, max_length=100)


class UpdateReleaseNoteDraftRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class UpdateReleaseChecklistRequest(BaseModel):
    change_scope_confirmed: bool
    rollback_plan_confirmed: bool
    release_window_confirmed: bool


router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.get("")
def bound_repositories(request: Request) -> list[dict[str, object]]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        repositories = session.scalars(
            select(Repository)
            .where(Repository.user_id == user.id)
            .order_by(Repository.updated_at.desc())
        )
        return [
            {
                "id": item.id,
                "full_name": item.full_name,
                "private": item.private,
                "webhook_configured": item.github_webhook_id is not None,
            }
            for item in repositories
        ]


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
                request.app.state.settings.github_webhook_enabled,
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
                "base_branch": item.base_branch,
                "head_sha": item.head_sha,
                "html_url": item.html_url,
                "merged_at": item.merged_at.isoformat() if item.merged_at else None,
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


@router.get("/{repository_id}/quality-gate")
def quality_gate(request: Request, repository_id: int) -> dict[str, object]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        repository = _require_owned_repository(session, repository_id, user.id)
        return evaluate_release_quality(session, repository).as_dict()


@router.get("/{repository_id}/release-notes/draft")
def release_note_draft(request: Request, repository_id: int) -> dict[str, object]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        repository = _require_owned_repository(session, repository_id, user.id)
        draft = get_release_note_draft(session, repository)
        if draft is None:
            raise HTTPException(status_code=404, detail="Release Notes 草稿不存在")
        return release_note_draft_payload(session, draft)


@router.post("/{repository_id}/release-notes/draft")
def create_release_note_draft(
    request: Request,
    repository_id: int,
    body: GenerateReleaseNoteDraftRequest,
) -> dict[str, object]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        repository = _require_owned_repository(session, repository_id, user.id)
        draft = generate_release_note_draft(session, repository, body.version)
        return release_note_draft_payload(session, draft)


@router.put("/{repository_id}/release-notes/draft")
def save_release_note_draft(
    request: Request,
    repository_id: int,
    body: UpdateReleaseNoteDraftRequest,
) -> dict[str, object]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        repository = _require_owned_repository(session, repository_id, user.id)
        try:
            draft = update_release_note_draft(session, repository, body.content)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return release_note_draft_payload(session, draft)


@router.get("/{repository_id}/release-readiness")
def release_readiness(request: Request, repository_id: int) -> dict[str, object]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        repository = _require_owned_repository(session, repository_id, user.id)
        return release_readiness_payload(session, repository)


@router.put("/{repository_id}/release-readiness")
def save_release_checklist(
    request: Request,
    repository_id: int,
    body: UpdateReleaseChecklistRequest,
) -> dict[str, object]:
    user = get_current_user(request)
    with request.app.state.session_factory() as session:
        repository = _require_owned_repository(session, repository_id, user.id)
        try:
            return update_release_checklist(
                session,
                repository,
                user.id,
                body.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{repository_id}/sync")
def sync_repository(request: Request, repository_id: int) -> dict[str, int]:
    user = get_current_user(request)
    try:
        with request.app.state.session_factory() as session:
            repository = _require_owned_repository(session, repository_id, user.id)
            return sync_repository_data(
                session,
                user,
                repository,
                request.app.state.github_client,
                request.app.state.token_cipher,
            )
    except GitHubApiError as exc:
        status_code = exc.status_code if exc.status_code in {403, 404, 429} else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def _require_owned_repository(session, repository_id: int, user_id: int) -> Repository:
    repository = session.scalar(
        select(Repository).where(Repository.id == repository_id, Repository.user_id == user_id)
    )
    if repository is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return repository
