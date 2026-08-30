from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import PullRequest, Release, Repository, WebhookEvent, WorkflowRun
from app.events.parser import ParsedEvent, parse_event


class EventService:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def ingest(
        self, repository_id: int, delivery_id: str, event_name: str, payload: dict
    ) -> WebhookEvent:
        with self.session_factory() as session:
            repository = session.get(Repository, repository_id)
            if repository is None:
                raise ValueError("仓库不存在")
            event = session.scalar(
                select(WebhookEvent).where(
                    WebhookEvent.repository_id == repository_id,
                    WebhookEvent.delivery_id == delivery_id,
                )
            )
            if event is None:
                event = WebhookEvent(
                    repository_id=repository_id,
                    delivery_id=delivery_id,
                    event_type=event_name,
                    raw_payload=json.dumps(payload, ensure_ascii=False),
                )
                session.add(event)
                session.commit()
                session.refresh(event)
            return event

    def process(self, event_id: int) -> None:
        with self.session_factory() as session:
            event = session.get(WebhookEvent, event_id)
            if event is None:
                raise ValueError("事件不存在")
            try:
                parsed = parse_event(event.event_type, json.loads(event.raw_payload))
            except (KeyError, TypeError, ValueError):
                event.status = "failed"
                session.commit()
                return
            if parsed.kind == "ignored":
                event.status = "ignored"
            else:
                repository = session.get(Repository, event.repository_id)
                if repository is None or repository.full_name != parsed.repository_full_name:
                    event.status = "failed"
                    session.commit()
                    raise ValueError("事件仓库与绑定仓库不匹配")
                self._upsert_business_state(session, repository.id, parsed)
                event.status = "processed"
            session.commit()

    @staticmethod
    def _upsert_business_state(session: Session, repository_id: int, parsed: ParsedEvent) -> None:
        if parsed.kind == "pull_request":
            item = session.scalar(
                select(PullRequest).where(
                    PullRequest.repository_id == repository_id,
                    PullRequest.number == parsed.number,
                )
            )
            if item is None:
                item = PullRequest(
                    repository_id=repository_id,
                    github_id=parsed.external_id or parsed.number or 0,
                    number=parsed.number or 0,
                    title=parsed.title or "",
                    body=parsed.body,
                    state=parsed.state or "unknown",
                )
                session.add(item)
            item.title = parsed.title or item.title
            item.body = parsed.body
            item.state = parsed.state or item.state
            item.head_branch = parsed.branch
            item.base_branch = parsed.base_branch
            item.head_sha = parsed.commit_sha
            item.author_login = parsed.author_login
            item.html_url = parsed.html_url
            item.merged_at = _parse_datetime(parsed.merged_at)
        elif parsed.kind == "workflow_run":
            item = session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.repository_id == repository_id,
                    WorkflowRun.github_id == parsed.external_id,
                )
            )
            if item is None:
                item = WorkflowRun(
                    repository_id=repository_id,
                    github_id=parsed.external_id or 0,
                    workflow_name=parsed.workflow_name or "",
                    status=parsed.state or "unknown",
                )
                session.add(item)
            item.workflow_name = parsed.workflow_name or item.workflow_name
            item.status = parsed.state or item.status
            item.conclusion = parsed.conclusion
            item.branch = parsed.branch
            item.commit_sha = parsed.commit_sha
            item.html_url = parsed.html_url
        elif parsed.kind == "release":
            item = session.scalar(
                select(Release).where(
                    Release.repository_id == repository_id,
                    Release.github_id == parsed.external_id,
                )
            )
            if item is None:
                item = Release(
                    repository_id=repository_id,
                    github_id=parsed.external_id or 0,
                    tag_name=parsed.tag_name or "",
                )
                session.add(item)
            item.tag_name = parsed.tag_name or item.tag_name
            item.name = parsed.title
            item.body = parsed.body
            item.published_at = _parse_datetime(parsed.published_at)
            item.html_url = parsed.html_url


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
