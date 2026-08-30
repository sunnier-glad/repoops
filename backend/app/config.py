from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+pysqlite:///:memory:"
    redis_url: str = "redis://redis:6379/0"
    celery_enabled: bool = False
    session_secret: str = "development-session-secret"

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    frontend_url: str = "http://localhost:5174/"
    github_webhook_base_url: str = "http://localhost:8000"
    github_webhook_enabled: bool = True
    github_token_encryption_key: str = ""

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    def validate_runtime(self) -> None:
        if self.app_env.lower() != "production":
            return

        required = {
            "GITHUB_CLIENT_ID": self.github_client_id,
            "GITHUB_CLIENT_SECRET": self.github_client_secret,
            "SESSION_SECRET": self.session_secret,
            "GITHUB_TOKEN_ENCRYPTION_KEY": self.github_token_encryption_key,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"生产配置缺少：{', '.join(missing)}")
