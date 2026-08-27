from __future__ import annotations

import json

from sqlalchemy import select

from app.ai.client import DeepSeekClient
from app.ai.service import AiService
from app.config import Settings
from app.db.models import AiAnalysis, Job, PullRequest, Release, WorkflowRun
from app.db.session import create_database_engine, create_session_factory
from app.events.service import EventService
from app.jobs.celery_app import celery_app


def _session_factory():
    settings = Settings()
    return create_session_factory(create_database_engine(settings.database_url)), settings


@celery_app.task(bind=True, max_retries=3)
def process_webhook_event(self, event_id: int):
    service, factory = _service()
    job_id = _start_event_job(factory, event_id)
    try:
        service.process(event_id)
    except (ConnectionError, TimeoutError) as exc:
        raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1)) from exc
    _finish_job(factory, job_id, "succeeded")
    return {"event_id": event_id, "status": "processed"}


@celery_app.task(bind=True, max_retries=3)
def analyze_pull_request(self, pull_request_id: int):
    return _run_ai_analysis(self, PullRequest, pull_request_id, "pull_request_summary")


@celery_app.task(bind=True, max_retries=3)
def analyze_workflow_failure(self, workflow_run_id: int):
    return _run_ai_analysis(self, WorkflowRun, workflow_run_id, "workflow_failure_explanation")


@celery_app.task(bind=True, max_retries=3)
def generate_release_notes(self, release_id: int):
    return _run_ai_analysis(self, Release, release_id, "release_notes")


def _service():
    factory, _ = _session_factory()
    return EventService(factory), factory


def _start_event_job(factory, event_id: int) -> int:
    with factory() as session:
        job = session.scalar(
            select(Job).where(Job.event_id == event_id, Job.kind == "process_webhook_event")
        )
        if job is None:
            job = Job(kind="process_webhook_event", event_id=event_id)
            session.add(job)
        job.status = "running"
        job.attempts += 1
        session.commit()
        return job.id


def _finish_job(factory, job_id: int, status: str, error: str | None = None) -> None:
    with factory() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.status = status
            job.error_message = error
            session.commit()


def _run_ai_analysis(task, model_type, target_id: int, analysis_type: str):
    factory, settings = _session_factory()
    with factory() as session:
        target = session.get(model_type, target_id)
        if target is None:
            raise ValueError("分析目标不存在")
        client = DeepSeekClient(
            settings.llm_base_url, settings.llm_api_key, settings.llm_model
        )
        service = AiService(client, settings.llm_model)
        try:
            if analysis_type == "pull_request_summary":
                result = service.summarize_pull_request(target.title, target.body)
                input_summary = target.title
            elif analysis_type == "workflow_failure_explanation":
                logs = f"状态：{target.status}\n结论：{target.conclusion}\n提交：{target.commit_sha}"
                result = service.explain_workflow_failure(target.workflow_name, logs)
                input_summary = logs
            else:
                result = service.generate_release_notes(target.tag_name, target.body or "")
                input_summary = target.tag_name
            analysis = AiAnalysis(
                analysis_type=result.analysis_type,
                target_type=model_type.__name__,
                target_id=target_id,
                model=result.model,
                input_summary=input_summary,
                result_json=json.dumps(result.content, ensure_ascii=False),
                status="succeeded",
            )
        except Exception as exc:  # noqa: BLE001 - AI failure must become an analysis record
            analysis = AiAnalysis(
                analysis_type=analysis_type,
                target_type=model_type.__name__,
                target_id=target_id,
                model=settings.llm_model,
                input_summary="",
                status="failed",
                error_message=str(exc),
            )
        session.add(analysis)
        session.commit()
        return {"analysis_id": analysis.id, "status": analysis.status}
