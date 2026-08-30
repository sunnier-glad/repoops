from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PullRequest, ReleaseNoteDraft, Repository, WorkflowRun


@dataclass(frozen=True)
class QualityCheck:
    key: str
    status: str
    title: str
    detail: str
    url: str | None = None


@dataclass(frozen=True)
class QualityGate:
    status: str
    summary: str
    checks: tuple[QualityCheck, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": self.summary,
            "checks": [asdict(check) for check in self.checks],
        }


def evaluate_release_quality(session: Session, repository: Repository) -> QualityGate:
    checks = (
        _default_branch_ci_check(session, repository),
        _open_pull_requests_check(session, repository),
        _release_notes_check(session, repository),
    )
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return QualityGate(
            status="blocked",
            summary="主分支 CI 未通过，暂不建议发布",
            checks=checks,
        )
    if "warning" in statuses:
        return QualityGate(
            status="warning",
            summary="存在发布前需要人工确认的风险",
            checks=checks,
        )
    return QualityGate(
        status="ready",
        summary="关键质量检查已通过，可以进入人工发布确认",
        checks=checks,
    )


def _default_branch_ci_check(session: Session, repository: Repository) -> QualityCheck:
    run = session.scalar(
        select(WorkflowRun)
        .where(
            WorkflowRun.repository_id == repository.id,
            WorkflowRun.branch == repository.default_branch,
        )
        .order_by(WorkflowRun.github_id.desc())
        .limit(1)
    )
    if run is None:
        return QualityCheck(
            key="default_branch_ci",
            status="warning",
            title="主分支 CI",
            detail=f"尚未同步到 {repository.default_branch} 分支的 CI 记录",
        )
    if run.status != "completed":
        return QualityCheck(
            key="default_branch_ci",
            status="warning",
            title="主分支 CI",
            detail=f"{run.workflow_name} 仍在运行，当前状态为 {run.status}",
            url=run.html_url,
        )
    if run.conclusion == "success":
        return QualityCheck(
            key="default_branch_ci",
            status="pass",
            title="主分支 CI",
            detail=f"最新一次 {run.workflow_name} 已通过",
            url=run.html_url,
        )
    return QualityCheck(
        key="default_branch_ci",
        status="fail",
        title="主分支 CI",
        detail=f"最新一次 {run.workflow_name} 结论为 {run.conclusion or 'unknown'}",
        url=run.html_url,
    )


def _open_pull_requests_check(session: Session, repository: Repository) -> QualityCheck:
    count = session.scalar(
        select(func.count(PullRequest.id)).where(
            PullRequest.repository_id == repository.id,
            PullRequest.state == "open",
        )
    )
    if count:
        return QualityCheck(
            key="open_pull_requests",
            status="warning",
            title="待处理 PR",
            detail=f"仍有 {count} 个开放 PR，需要确认是否纳入本次发布",
        )
    return QualityCheck(
        key="open_pull_requests",
        status="pass",
        title="待处理 PR",
        detail="没有待处理的开放 PR",
    )


def _release_notes_check(session: Session, repository: Repository) -> QualityCheck:
    draft = session.scalar(
        select(ReleaseNoteDraft).where(ReleaseNoteDraft.repository_id == repository.id)
    )
    if draft is None:
        return QualityCheck(
            key="release_notes",
            status="warning",
            title="发布说明",
            detail="尚未生成 Release Notes 草稿",
        )
    if draft.content.strip():
        return QualityCheck(
            key="release_notes",
            status="pass",
            title="发布说明",
            detail=f"{draft.version} 草稿已准备，包含 {draft.source_pr_count} 个来源 PR",
        )
    return QualityCheck(
        key="release_notes",
        status="warning",
        title="发布说明",
        detail=f"{draft.version} 草稿内容为空",
    )
