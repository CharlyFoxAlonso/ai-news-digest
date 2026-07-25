from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import EmailStr, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gemini-3.5-flash", alias="LLM_MODEL")
    llm_api_key: SecretStr | None = Field(default=None, alias="LLM_API_KEY")
    recipient_email: EmailStr = Field(alias="RECIPIENT_EMAIL")
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, ge=1, le=65535, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_app_password: SecretStr | None = Field(default=None, alias="SMTP_APP_PASSWORD")
    timezone: str = Field(default="America/Argentina/Buenos_Aires", alias="TIMEZONE")
    repository: str = Field(default="local/ai-news-digest", alias="REPOSITORY")
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    feed_timeout_seconds: float = Field(default=12.0, ge=1, le=60)
    max_feed_bytes: int = Field(default=2_000_000, ge=1024)
    max_entries_per_feed: int = Field(default=50, ge=1, le=200)
    state_dir: Path = Field(default=Path("."), alias="STATE_DIR")

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value != "gemini":
            raise ValueError("LLM_PROVIDER must be 'gemini'")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    def require_delivery_secrets(self) -> None:
        if self.dry_run:
            return
        missing = [
            name
            for name, value in (
                ("LLM_API_KEY", self.llm_api_key),
                ("SMTP_USERNAME", self.smtp_username),
                ("SMTP_APP_PASSWORD", self.smtp_app_password),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"missing required configuration: {', '.join(missing)}")
