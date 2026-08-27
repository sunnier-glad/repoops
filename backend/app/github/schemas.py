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


@dataclass(frozen=True)
class GitHubPullRequest:
    github_id: int
    number: int
    title: str
    body: str | None
    state: str
    head_branch: str | None
    head_sha: str | None
    author_login: str | None
    html_url: str | None


@dataclass(frozen=True)
class GitHubWorkflowRun:
    github_id: int
    workflow_name: str
    status: str
    conclusion: str | None
    branch: str | None
    commit_sha: str | None
    html_url: str | None


@dataclass(frozen=True)
class GitHubRelease:
    github_id: int
    tag_name: str
    name: str | None
    body: str | None
    published_at: str | None
    html_url: str | None
