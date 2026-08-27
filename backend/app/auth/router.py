from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.auth.service import upsert_github_identity
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/github")
def github_login(request: Request) -> RedirectResponse:
    service = request.app.state.oauth_service
    if service is None:
        raise HTTPException(status_code=503, detail="GitHub OAuth 尚未配置")
    return RedirectResponse(service.build_authorize_url())


@router.get("/github/callback")
def github_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    service = request.app.state.oauth_service
    if service is None:
        raise HTTPException(status_code=503, detail="GitHub OAuth 尚未配置")
    try:
        return_to, identity = service.complete_callback(state, code, request.app.state.github_client)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with request.app.state.session_factory() as session:
        user = upsert_github_identity(session, identity, request.app.state.token_cipher)
    request.session["user_id"] = user.id
    return RedirectResponse(return_to, status_code=303)


@router.get("/me")
def current_user(request: Request) -> dict[str, object]:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="未登录")
    with request.app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.id == user_id))
        if user is None or user.github_account is None:
            raise HTTPException(status_code=401, detail="会话已失效")
        return {"id": user.id, "github_login": user.github_account.login}
