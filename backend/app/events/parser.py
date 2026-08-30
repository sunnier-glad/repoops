from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedEvent:
    kind: str
    repository_full_name: str | None = None
    action: str | None = None
    branch: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    number: int | None = None
    external_id: int | None = None
    title: str | None = None
    body: str | None = None
    state: str | None = None
    conclusion: str | None = None
    tag_name: str | None = None
    published_at: str | None = None
    merged_at: str | None = None
    html_url: str | None = None
    workflow_name: str | None = None
    author_login: str | None = None


def parse_event(event_name: str, payload: dict) -> ParsedEvent:
    repository_full_name = payload.get("repository", {}).get("full_name")
    if event_name == "push":
        return ParsedEvent(
            kind="push",
            repository_full_name=repository_full_name,
            branch=_branch_from_ref(payload.get("ref")),
            commit_sha=payload.get("after"),
        )
    if event_name == "pull_request":
        pull_request = payload["pull_request"]
        return ParsedEvent(
            kind="pull_request",
            repository_full_name=repository_full_name,
            action=payload.get("action"),
            branch=pull_request.get("head", {}).get("ref"),
            base_branch=pull_request.get("base", {}).get("ref"),
            commit_sha=pull_request.get("head", {}).get("sha"),
            number=payload.get("number"),
            external_id=pull_request.get("id"),
            title=pull_request.get("title"),
            body=pull_request.get("body"),
            state=pull_request.get("state"),
            html_url=pull_request.get("html_url"),
            author_login=pull_request.get("user", {}).get("login"),
            merged_at=pull_request.get("merged_at"),
        )
    if event_name == "workflow_run":
        workflow_run = payload["workflow_run"]
        return ParsedEvent(
            kind="workflow_run",
            repository_full_name=repository_full_name,
            action=payload.get("action"),
            external_id=workflow_run.get("id"),
            workflow_name=workflow_run.get("name"),
            state=workflow_run.get("status"),
            conclusion=workflow_run.get("conclusion"),
            branch=workflow_run.get("head_branch"),
            commit_sha=workflow_run.get("head_sha"),
            html_url=workflow_run.get("html_url"),
        )
    if event_name == "release":
        release = payload["release"]
        return ParsedEvent(
            kind="release",
            repository_full_name=repository_full_name,
            action=payload.get("action"),
            external_id=release.get("id"),
            tag_name=release.get("tag_name"),
            title=release.get("name"),
            body=release.get("body"),
            published_at=release.get("published_at"),
            html_url=release.get("html_url"),
        )
    return ParsedEvent(kind="ignored", repository_full_name=repository_full_name)


def _branch_from_ref(ref: str | None) -> str | None:
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref and ref.startswith(prefix) else ref
