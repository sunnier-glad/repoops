from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import DeepSeekClient
from app.ai.service import AiService
from app.config import Settings
from app.db.models import AiAnalysis, PullRequest, ReleaseNoteDraft, Repository


def create_release_notes_polish(
    session: Session, repository: Repository, settings: Settings
) -> dict[str, object]:
    draft = _get_draft(session, repository)
    if draft is None:
        raise ValueError("请先生成 Release Notes 草稿")

    source_rows = session.scalars(
        select(PullRequest).where(
            PullRequest.repository_id == repository.id,
            PullRequest.number.in_(_source_numbers(draft.source_snapshot_json)),
        )
    )
    sources = "\n".join(
        f"#{item.number} {item.title}（作者：{item.author_login or '未知'}）"
        for item in source_rows
    )
    input_summary = f"{draft.version} · {draft.source_pr_count} 个来源 PR"
    analysis = AiAnalysis(
        analysis_type="release_notes_polish",
        target_type="ReleaseNoteDraft",
        target_id=draft.id,
        model=settings.llm_model,
        input_summary=input_summary,
        status="queued",
    )
    session.add(analysis)
    session.flush()
    try:
        client = DeepSeekClient(
            settings.llm_base_url, settings.llm_api_key, settings.llm_model
        )
        result = AiService(client, settings.llm_model).polish_release_notes(
            draft.version, draft.content, sources
        )
        payload = {
            "base_content": draft.content,
            "summary": result.content["summary"],
            "suggested_content": result.content["suggested_content"],
            "changes": result.content["changes"],
        }
        analysis.result_json = json.dumps(payload, ensure_ascii=False)
        analysis.status = "succeeded"
    except Exception as exc:  # noqa: BLE001 - AI failure is an auditable result
        analysis.status = "failed"
        analysis.error_message = str(exc)
    session.commit()
    session.refresh(analysis)
    return analysis_payload(analysis)


def get_latest_release_notes_polish(
    session: Session, repository: Repository
) -> dict[str, object] | None:
    draft = _get_draft(session, repository)
    if draft is None:
        return None
    analysis = session.scalar(
        select(AiAnalysis)
        .where(
            AiAnalysis.analysis_type == "release_notes_polish",
            AiAnalysis.target_type == "ReleaseNoteDraft",
            AiAnalysis.target_id == draft.id,
        )
        .order_by(AiAnalysis.id.desc())
        .limit(1)
    )
    if analysis is None:
        return None
    payload = analysis_payload(analysis)
    suggestion = payload["suggestion"]
    if (
        analysis.status == "succeeded"
        and (not isinstance(suggestion, dict) or suggestion.get("base_content") != draft.content)
    ):
        return None
    return payload


def analysis_payload(analysis: AiAnalysis) -> dict[str, object]:
    return {
        "id": analysis.id,
        "status": analysis.status,
        "model": analysis.model,
        "error": analysis.error_message,
        "suggestion": json.loads(analysis.result_json) if analysis.result_json else None,
        "created_at": analysis.created_at.isoformat(),
    }


def _get_draft(session: Session, repository: Repository) -> ReleaseNoteDraft | None:
    return session.scalar(
        select(ReleaseNoteDraft).where(
            ReleaseNoteDraft.repository_id == repository.id
        )
    )


def _source_numbers(snapshot_json: str) -> list[int]:
    try:
        snapshot = json.loads(snapshot_json)
    except json.JSONDecodeError:
        return []
    return [item["number"] for item in snapshot if isinstance(item, dict) and "number" in item]
