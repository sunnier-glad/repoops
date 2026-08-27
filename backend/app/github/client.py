from __future__ import annotations

import httpx

from app.auth.service import GitHubIdentity
from app.github.schemas import GitHubRepository, WebhookInfo


class GitHubApiError(RuntimeError):
    def __init__(self, status_code: int | None, message: str, retry_after: str | None = None):
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(message)


class GitHubClient:
    api_base_url = "https://api.github.com"
    oauth_token_url = "https://github.com/login/oauth/access_token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self._client = httpx.Client(transport=transport, timeout=timeout)

    def exchange_code(self, code: str) -> str:
        response = self._send(
            "POST",
            self.oauth_token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        access_token = response.json().get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GitHubApiError(response.status_code, "GitHub OAuth 响应缺少 access_token")
        return access_token

    def get_identity(self, access_token: str) -> GitHubIdentity:
        response = self._send("GET", f"{self.api_base_url}/user", token=access_token)
        data = response.json()
        return GitHubIdentity(
            github_user_id=data["id"],
            login=data["login"],
            name=data.get("name"),
            avatar_url=data.get("avatar_url"),
            access_token=access_token,
        )

    def list_repositories(self, access_token: str) -> list[GitHubRepository]:
        response = self._send(
            "GET",
            f"{self.api_base_url}/user/repos",
            token=access_token,
            params={"per_page": 100, "sort": "updated"},
        )
        return [
            GitHubRepository(
                github_id=item["id"],
                full_name=item["full_name"],
                name=item["name"],
                private=item["private"],
            )
            for item in response.json()
        ]

    def create_webhook(
        self, access_token: str, repository: str, callback_url: str, secret: str
    ) -> WebhookInfo:
        response = self._send(
            "POST",
            f"{self.api_base_url}/repos/{repository}/hooks",
            token=access_token,
            json={
                "name": "web",
                "active": True,
                "events": ["push", "pull_request", "workflow_run", "release"],
                "config": {
                    "url": callback_url,
                    "content_type": "json",
                    "insecure_ssl": "0",
                    "secret": secret,
                },
            },
        )
        data = response.json()
        return WebhookInfo(id=data["id"], active=data["active"])

    def close(self) -> None:
        self._client.close()

    def _send(self, method: str, url: str, *, token: str | None = None, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("Accept", "application/vnd.github+json")
        headers.setdefault("X-GitHub-Api-Version", "2022-11-28")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self._client.request(method, url, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise GitHubApiError(None, "GitHub API 网络请求失败") from exc
        if response.is_error:
            try:
                message = response.json().get("message", "GitHub API 请求失败")
            except ValueError:
                message = "GitHub API 请求失败"
            raise GitHubApiError(response.status_code, message, response.headers.get("Retry-After"))
        return response
