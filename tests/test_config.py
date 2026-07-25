import pytest
from pydantic import ValidationError

from ai_news.config import Settings


def test_valid_configuration() -> None:
    settings = Settings(
        RECIPIENT_EMAIL="reader@example.com",
        LLM_API_KEY="key",
        SMTP_USERNAME="sender@example.com",
        SMTP_APP_PASSWORD="password",
    )
    settings.require_delivery_secrets()
    assert settings.llm_provider == "gemini"
    assert settings.smtp_port == 587


def test_incomplete_configuration() -> None:
    settings = Settings(RECIPIENT_EMAIL="reader@example.com")
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        settings.require_delivery_secrets()


def test_invalid_email() -> None:
    with pytest.raises(ValidationError):
        Settings(RECIPIENT_EMAIL="not-an-email")


def test_dry_run_does_not_require_secrets() -> None:
    Settings(RECIPIENT_EMAIL="reader@example.com", DRY_RUN=True).require_delivery_secrets()
