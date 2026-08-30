from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PullRequest, Release, ReleaseNoteDraft, Repository


def generate_release_note_draft(
    session: Session, repository: Repository, version: str
) -> ReleaseNoteDraft:
    normalized_version = version.strip()
    if not normalized_version:
        raise ValueError("版本号不能为空")

    latest_release = session.scalar(
        select(Release)
        .where(
            Release.repository_id == repository.id,
            Release.published_at.is_not(None),
        )
        .order_by(Release.published_at.desc(), Release.github_id.desc())
        .limit(1)
    )
    conditions = [
        PullRequest.repository_id == repository.id,
        PullRequest.base_branch == repository.default_branch,
        PullRequest.merged_at.is_not(None),
    ]
    if latest_release is not None:
        conditions.append(PullRequest.merged_at > latest_release.published_at)
    pull_requests = list(
        session.scalars(
            select(PullRequest)
            .where(*conditions)
            .order_by(PullRequest.merged_at.asc(), PullRequest.number.asc())
        )
    )
    sources = [_source_snapshot(item) for item in pull_requests]
    content = _render_markdown(normalized_version, latest_release, sources)

    draft = session.scalar(
        select(ReleaseNoteDraft).where(ReleaseNoteDraft.repository_id == repository.id)
    )
    if draft is None:
        draft = ReleaseNoteDraft(repository_id=repository.id)
        session.add(draft)
    draft.version = normalized_version
    draft.content = content
    draft.source_snapshot_json = json.dumps(sources, ensure_ascii=False)
    draft.source_pr_count = len(sources)
    draft.based_on_release_id = latest_release.id if latest_release else None
    session.commit()
    session.refresh(draft)
    return draft


def get_release_note_draft(
    session: Session, repository: Repository
) -> ReleaseNoteDraft | None:
    return session.scalar(
        select(ReleaseNoteDraft).where(ReleaseNoteDraft.repository_id == repository.id)
    )


def update_release_note_draft(
    session: Session, repository: Repository, content: str
) -> ReleaseNoteDraft:
    draft = get_release_note_draft(session, repository)
    if draft is None:
        raise ValueError("Release Notes 草稿不存在")
    if not content.strip():
        raise ValueError("草稿内容不能为空")
    draft.content = content
    session.commit()
    session.refresh(draft)
    return draft


def release_note_draft_payload(
    session: Session, draft: ReleaseNoteDraft
) -> dict[str, object]:
    based_on_release = (
        session.get(Release, draft.based_on_release_id)
        if draft.based_on_release_id is not None
        else None
    )
    return {
        "id": draft.id,
        "repository_id": draft.repository_id,
        "version": draft.version,
        "content": draft.content,
        "source_pr_count": draft.source_pr_count,
        "sources": json.loads(draft.source_snapshot_json),
        "based_on_release": (
            {
                "id": based_on_release.id,
                "tag_name": based_on_release.tag_name,
                "published_at": based_on_release.published_at.isoformat(),
            }
            if based_on_release and based_on_release.published_at
            else None
        ),
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }


def _source_snapshot(item: PullRequest) -> dict[str, object]:
    return {
        "number": item.number,
        "title": item.title,
        "author_login": item.author_login,
        "html_url": item.html_url,
        "merged_at": item.merged_at.isoformat() if item.merged_at else None,
    }


def _render_markdown(
    version: str, latest_release: Release | None, sources: list[dict[str, object]]
) -> str:
    if latest_release is None:
        baseline = "仓库开始记录以来"
    else:
        baseline = f"{latest_release.tag_name} 发布之后"
    lines = [
        f"# {version}",
        "",
        f"> 根据 {baseline}合并到默认分支的 PR 生成，共 {len(sources)} 项。",
        "",
        "## 变更内容",
        "",
    ]
    if not sources:
        lines.append("- 暂无符合条件的已合并 PR。")
    for source in sources:
        number = source["number"]
        title = source["title"]
        url = source["html_url"]
        author = source["author_login"]
        reference = f"[#{number}]({url})" if url else f"#{number}"
        suffix = f"（@{author}）" if author else ""
        lines.append(f"- {reference} {title}{suffix}")
    return "\n".join(lines) + "\n"
