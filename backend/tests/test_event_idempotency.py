from app.db.models import Base, PullRequest, Repository, User, WebhookEvent
from app.db.session import create_database_engine, create_session_factory
from app.events.service import EventService


def make_service(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'events.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        user = User()
        session.add(user)
        session.flush()
        repository = Repository(
            user_id=user.id,
            github_id=101,
            owner="octocat",
            name="demo",
            full_name="octocat/demo",
            private=False,
            encrypted_webhook_secret="unused",
        )
        session.add(repository)
        session.commit()
        repository_id = repository.id
    return EventService(factory), repository_id, factory


def test_same_delivery_is_ingested_once_and_processing_is_idempotent(tmp_path):
    service, repository_id, factory = make_service(tmp_path)
    payload = {
        "action": "opened",
        "number": 12,
        "repository": {"full_name": "octocat/demo"},
        "pull_request": {
            "title": "Improve docs",
            "body": "Details",
            "state": "open",
            "head": {"ref": "feature/docs", "sha": "def456"},
            "html_url": "https://github.com/octocat/demo/pull/12",
            "user": {"login": "octocat"},
        },
    }

    first = service.ingest(repository_id, "delivery-1", "pull_request", payload)
    second = service.ingest(repository_id, "delivery-1", "pull_request", payload)
    service.process(first.id)
    service.process(first.id)

    assert first.id == second.id
    with factory() as session:
        assert session.query(WebhookEvent).count() == 1
        assert session.query(PullRequest).count() == 1


def test_malformed_event_is_marked_failed_and_keeps_raw_payload(tmp_path):
    service, repository_id, factory = make_service(tmp_path)
    with factory() as session:
        event = WebhookEvent(
            repository_id=repository_id,
            delivery_id="delivery-bad",
            event_type="pull_request",
            raw_payload="{not-json",
        )
        session.add(event)
        session.commit()
        event_id = event.id

    service.process(event_id)

    with factory() as session:
        event = session.get(WebhookEvent, event_id)
        assert event.status == "failed"
        assert event.raw_payload == "{not-json"
