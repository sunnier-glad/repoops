import pytest

from app.config import Settings


def test_development_settings_have_local_defaults():
    settings = Settings()

    assert settings.app_env == "development"
    assert settings.app_version == "0.1.0"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.github_webhook_enabled is True


def test_production_settings_require_github_oauth_and_encryption():
    settings = Settings(app_env="production")

    with pytest.raises(ValueError, match="GITHUB_CLIENT_ID"):
        settings.validate_runtime()
