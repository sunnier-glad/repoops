from __future__ import annotations

from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import TokenCipher
from app.db.models import Repository, User
from app.github.client import GitHubApiError, GitHubClient


def github_access_token(user: User, cipher: TokenCipher) -> str:
    if user.github_account is None:
        raise HTTPException(status_code=401, detail="未绑定 GitHub 账号")
    return cipher.decrypt(user.github_account.encrypted_access_token)


def list_available_repositories(user: User, github: GitHubClient, cipher: TokenCipher):
    return github.list_repositories(github_access_token(user, cipher))


def bind_repository(
    session: Session,
    user: User,
    full_name: str,
    github: GitHubClient,
    cipher: TokenCipher,
    callback_base_url: str,
) -> Repository:
    available = list_available_repositories(user, github, cipher)
    selected = next((item for item in available if item.full_name == full_name), None)
    if selected is None:
        raise HTTPException(status_code=403, detail="当前 GitHub 账号无权访问该仓库")
    existing = session.scalar(
        select(Repository).where(
            Repository.user_id == user.id, Repository.github_id == selected.github_id
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="仓库已经绑定")

    owner, separator, name = selected.full_name.partition("/")
    if not separator or not owner or not name:
        raise HTTPException(status_code=400, detail="仓库名称格式无效")
    secret = token_urlsafe(32)
    repository = Repository(
        user_id=user.id,
        github_id=selected.github_id,
        owner=owner,
        name=name,
        full_name=selected.full_name,
        private=selected.private,
        encrypted_webhook_secret=cipher.encrypt(secret),
    )
    session.add(repository)
    session.flush()
    try:
        hook = github.create_webhook(
            github_access_token(user, cipher),
            selected.full_name,
            f"{callback_base_url.rstrip('/')}/api/webhooks/github/{repository.id}",
            secret,
        )
    except GitHubApiError:
        session.rollback()
        raise
    repository.github_webhook_id = hook.id
    session.commit()
    session.refresh(repository)
    return repository
