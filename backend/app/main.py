from cryptography.fernet import Fernet
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.auth.router import router as auth_router
from app.auth.service import OAuthService, OAuthStateStore, TokenCipher
from app.config import Settings
from app.db.models import Base
from app.db.session import create_database_engine, create_session_factory
from app.github.client import GitHubClient
from app.github.router import router as github_router
from app.webhooks.router import router as webhook_router

APP_VERSION = "0.1.0"


def create_app(
    *, settings: Settings | None = None, github_client=None
) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="RepoOps API", version=APP_VERSION)
    engine = create_database_engine(settings.database_url)
    if settings.app_env != "production":
        Base.metadata.create_all(engine)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=settings.app_env == "production",
    )
    app.state.settings = settings
    app.state.session_factory = create_session_factory(engine)
    app.state.oauth_service = (
        OAuthService(
            client_id=settings.github_client_id,
            redirect_uri=settings.github_redirect_uri,
            state_store=OAuthStateStore(),
        )
        if settings.github_client_id.strip()
        else None
    )
    app.state.github_client = github_client or (
        GitHubClient(settings.github_client_id, settings.github_client_secret)
        if settings.github_client_id.strip()
        else None
    )
    app.state.token_cipher = TokenCipher(
        settings.github_token_encryption_key or Fernet.generate_key()
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION}

    app.include_router(auth_router)
    app.include_router(github_router)
    app.include_router(webhook_router)
    return app


app = create_app()
