from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubRepository:
    github_id: int
    full_name: str
    name: str
    private: bool


@dataclass(frozen=True)
class WebhookInfo:
    id: int
    active: bool
