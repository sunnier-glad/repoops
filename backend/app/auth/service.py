from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from time import time
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GitHubAccount, User


class OAuthStateStore:
    def __init__(self, ttl_seconds: int = 300):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds 必须大于 0")
        self.ttl_seconds = ttl_seconds
        self._states: dict[str, tuple[float, str]] = {}

    def issue(self, return_to: str) -> str:
        state = token_urlsafe(32)
        self._states[state] = (time() + self.ttl_seconds, return_to)
        return state

    def consume(self, state: str) -> str | None:
        record = self._states.pop(state, None)
        if record is None:
            return None
        expires_at, return_to = record
        if expires_at <= time():
            return None
        return return_to


@dataclass(frozen=True)
class GitHubIdentity:
    github_user_id: int
    login: str
    name: str | None
    avatar_url: str | None
    access_token: str


class OAuthService:
    authorize_url = "https://github.com/login/oauth/authorize"
    scope = "read:user repo admin:repo_hook"

    def __init__(self, client_id: str, redirect_uri: str, state_store: OAuthStateStore):
        if not client_id.strip():
            raise ValueError("client_id 不能为空")
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.state_store = state_store

    def build_authorize_url(self, return_to: str = "/") -> str:
        state = self.state_store.issue(return_to)
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": self.scope,
                "state": state,
            }
        )
        return f"{self.authorize_url}?{query}"

    def complete_callback(self, state: str, code: str, client) -> tuple[str, GitHubIdentity]:
        return_to = self.state_store.consume(state)
        if return_to is None:
            raise ValueError("OAuth state 无效或已过期")
        if not code.strip():
            raise ValueError("OAuth code 不能为空")
        access_token = client.exchange_code(code)
        return return_to, client.get_identity(access_token)


class TokenCipher:
    def __init__(self, key: bytes | str):
        self._cipher = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self._cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        return self._cipher.decrypt(ciphertext.encode("ascii")).decode("utf-8")


def upsert_github_identity(session: Session, identity: GitHubIdentity, cipher: TokenCipher) -> User:
    account = session.scalar(
        select(GitHubAccount).where(GitHubAccount.github_user_id == identity.github_user_id)
    )
    if account is None:
        user = User()
        session.add(user)
        session.flush()
        account = GitHubAccount(user_id=user.id, github_user_id=identity.github_user_id, login=identity.login,
                                name=identity.name, avatar_url=identity.avatar_url,
                                encrypted_access_token=cipher.encrypt(identity.access_token))
        session.add(account)
    else:
        user = account.user
        account.login = identity.login
        account.name = identity.name
        account.avatar_url = identity.avatar_url
        account.encrypted_access_token = cipher.encrypt(identity.access_token)
    session.commit()
    session.refresh(user)
    return user
