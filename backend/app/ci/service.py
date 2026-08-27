from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Repository, WorkflowRun


def list_failed_workflows(session: Session, user_id: int) -> list[WorkflowRun]:
    return list(
        session.scalars(
            select(WorkflowRun)
            .join(Repository, Repository.id == WorkflowRun.repository_id)
            .where(Repository.user_id == user_id, WorkflowRun.conclusion == "failure")
            .order_by(WorkflowRun.updated_at.desc())
        )
    )
