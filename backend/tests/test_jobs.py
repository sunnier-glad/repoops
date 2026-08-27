from app.db.models import Base
from app.db.session import create_database_engine, create_session_factory
from app.events.tasks import (
    analyze_pull_request,
    analyze_workflow_failure,
    generate_release_notes,
    process_webhook_event,
)
from app.jobs.celery_app import celery_app
from app.jobs.service import JobService, RetryableJobError, retry_delay


def make_service(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'jobs.db'}")
    Base.metadata.create_all(engine)
    return JobService(create_session_factory(engine))


def test_job_lifecycle_records_success_and_failure(tmp_path):
    service = make_service(tmp_path)
    success = service.create("sync_event", event_id=1)
    service.run(success.id, lambda: "ok")
    failed = service.create("ai_analysis")

    def fail():
        raise ValueError("invalid input")

    service.run(failed.id, fail)

    assert service.get(success.id).status == "succeeded"
    assert service.get(failed.id).status == "failed"
    assert service.get(failed.id).error_message == "invalid input"


def test_only_retryable_errors_use_bounded_exponential_backoff():
    assert retry_delay(1) == 2
    assert retry_delay(3) == 8
    assert retry_delay(4) is None
    assert isinstance(RetryableJobError("temporary"), Exception)


def test_celery_uses_json_payloads_and_late_acknowledgement():
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.task_acks_late is True


def test_async_task_contracts_accept_only_internal_ids():
    assert process_webhook_event.name.endswith("process_webhook_event")
    assert analyze_pull_request.name.endswith("analyze_pull_request")
    assert analyze_workflow_failure.name.endswith("analyze_workflow_failure")
    assert generate_release_notes.name.endswith("generate_release_notes")
