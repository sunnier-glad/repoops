from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GitHubAccount, ReleaseChecklist, ReleaseNoteDraft, Repository
from app.quality.service import evaluate_release_quality

MANUAL_CHECKS = (
    (
        "change_scope_confirmed",
        "变更范围已确认",
        "已核对本次版本包含的功能、修复和不包含项。",
    ),
    (
        "rollback_plan_confirmed",
        "回滚方案已准备",
        "已确认出现异常时的回滚版本、步骤和负责人。",
    ),
    (
        "release_window_confirmed",
        "发布窗口已确认",
        "已确认发布时间、观察窗口和发布后的验证方式。",
    ),
)


def update_release_checklist(
    session: Session,
    repository: Repository,
    user_id: int,
    confirmations: dict[str, bool],
) -> dict[str, object]:
    draft = session.scalar(
        select(ReleaseNoteDraft).where(ReleaseNoteDraft.repository_id == repository.id)
    )
    if draft is None:
        raise ValueError("请先生成 Release Notes 草稿")

    checklist = session.scalar(
        select(ReleaseChecklist).where(ReleaseChecklist.repository_id == repository.id)
    )
    if checklist is None:
        checklist = ReleaseChecklist(repository_id=repository.id, version=draft.version)
        session.add(checklist)

    checklist.version = draft.version
    for key, _, _ in MANUAL_CHECKS:
        setattr(checklist, key, confirmations[key])
    checklist.confirmed_by_user_id = user_id
    session.commit()
    return release_readiness_payload(session, repository)


def release_readiness_payload(session: Session, repository: Repository) -> dict[str, object]:
    gate = evaluate_release_quality(session, repository)
    draft = session.scalar(
        select(ReleaseNoteDraft).where(ReleaseNoteDraft.repository_id == repository.id)
    )
    checklist = session.scalar(
        select(ReleaseChecklist).where(ReleaseChecklist.repository_id == repository.id)
    )
    active_checklist = (
        checklist
        if draft is not None and checklist is not None and checklist.version == draft.version
        else None
    )
    manual_checks = [
        {
            "key": key,
            "title": title,
            "detail": detail,
            "confirmed": bool(getattr(active_checklist, key, False)),
        }
        for key, title, detail in MANUAL_CHECKS
    ]
    automated_checks = gate.as_dict()["checks"]
    completed = sum(item["status"] == "pass" for item in automated_checks) + sum(
        item["confirmed"] for item in manual_checks
    )
    total = len(automated_checks) + len(manual_checks)

    if gate.status == "blocked":
        status = "blocked"
        summary = "自动检查存在阻塞项，暂不能进入发布确认"
    elif gate.status == "warning":
        status = "warning"
        summary = "自动检查仍有风险项，需要处理或确认"
    elif completed < total:
        status = "pending"
        summary = "自动检查已通过，请完成人工发布确认"
    else:
        status = "ready"
        summary = "自动检查与人工确认均已完成，可以进入人工发布操作"

    updated_by = None
    if active_checklist and active_checklist.confirmed_by_user_id:
        updated_by = session.scalar(
            select(GitHubAccount.login).where(
                GitHubAccount.user_id == active_checklist.confirmed_by_user_id
            )
        )

    return {
        "status": status,
        "summary": summary,
        "ready_to_release": status == "ready",
        "version": draft.version if draft else None,
        "automated_checks": automated_checks,
        "manual_checks": manual_checks,
        "progress": {"completed": completed, "total": total},
        "updated_by": updated_by,
        "updated_at": (active_checklist.updated_at.isoformat() if active_checklist else None),
    }
