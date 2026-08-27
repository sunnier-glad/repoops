from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.db.models import Job, Repository, WebhookEvent
from app.events.tasks import process_webhook_event
from app.webhooks.security import verify_signature

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/github/{repository_id}", status_code=202)
async def receive_github_webhook(repository_id: int, request: Request) -> JSONResponse:
    payload = await request.body()
    delivery_id = request.headers.get("X-GitHub-Delivery")
    event_type = request.headers.get("X-GitHub-Event")
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not delivery_id or not event_type:
        raise HTTPException(status_code=400, detail="Webhook headers 缺失")

    with request.app.state.session_factory() as session:
        repository = session.scalar(select(Repository).where(Repository.id == repository_id))
        if repository is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        secret = request.app.state.token_cipher.decrypt(repository.encrypted_webhook_secret)
        if not verify_signature(payload, signature, secret):
            raise HTTPException(status_code=401, detail="Webhook 签名无效")
        duplicate = session.scalar(
            select(WebhookEvent).where(
                WebhookEvent.repository_id == repository_id,
                WebhookEvent.delivery_id == delivery_id,
            )
        )
        if duplicate is not None:
            return JSONResponse(status_code=202, content={"status": "accepted", "duplicate": True})
        event = WebhookEvent(
                repository_id=repository_id,
                delivery_id=delivery_id,
                event_type=event_type,
                raw_payload=payload.decode("utf-8"),
            )
        session.add(event)
        session.commit()
        event_id = event.id
        session.add(Job(kind="process_webhook_event", event_id=event_id))
        session.commit()
    if request.app.state.settings.celery_enabled:
        process_webhook_event.delay(event_id)
    return JSONResponse(status_code=202, content={"status": "accepted", "duplicate": False})
