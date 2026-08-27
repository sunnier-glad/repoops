from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import sessionmaker

from app.db.models import Job


class RetryableJobError(RuntimeError):
    """A temporary dependency failure that may be retried."""


def retry_delay(attempt: int) -> int | None:
    return 2**attempt if 1 <= attempt <= 3 else None


class JobService:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def create(self, kind: str, event_id: int | None = None) -> Job:
        with self.session_factory() as session:
            job = Job(kind=kind, event_id=event_id)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def get(self, job_id: int) -> Job:
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise ValueError("任务不存在")
            session.expunge(job)
            return job

    def run(self, job_id: int, handler: Callable[[], object]) -> None:
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise ValueError("任务不存在")
            job.status = "running"
            job.attempts += 1
            session.commit()
        try:
            handler()
        except Exception as exc:  # noqa: BLE001 - persist every handler failure as job state
            with self.session_factory() as session:
                job = session.get(Job, job_id)
                job.status = "failed"
                job.error_message = str(exc)
                session.commit()
            return
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            job.status = "succeeded"
            job.error_message = None
            session.commit()
