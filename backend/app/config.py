from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Quotient"
    environment: str = "development"
    api_prefix: str = "/api"
    app_url: str = "http://localhost:5173"

    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'quotient.db'}"

    secret_key: str = "dev-only-insecure-secret-key-change-me"
    access_token_ttl_minutes: int = 60
    cookie_name: str = "quotient_session"
    csrf_cookie_name: str = "quotient_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_secure: bool = False
    cookie_domain: str | None = None

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    trusted_proxy_hops: int = 0

    rate_limit_enabled: bool = True
    rate_limit_default: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_auth: int = 10
    rate_limit_auth_window_seconds: int = 60
    rate_limit_public: int = 30
    rate_limit_public_window_seconds: int = 60

    uploads_dir: Path = PROJECT_ROOT / "data" / "uploads"
    max_upload_bytes: int = 2 * 1024 * 1024
    max_request_bytes: int = 8 * 1024 * 1024
    allowed_upload_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["image/png", "image/jpeg", "image/webp"]
    )

    payments_provider: str = "mock"
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None
    mock_webhook_secret: str = "mock-webhook-secret"
    plan_price_cents: int = 1900
    plan_currency: str = "usd"

    admin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)
    log_level: str = "INFO"

    @field_validator("cors_origins", "allowed_hosts", "allowed_upload_types", "admin_emails", mode="before")
    @classmethod
    def _parse_csv(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("admin_emails")
    @classmethod
    def _lower_emails(cls, value: list[str]) -> list[str]:
        return [item.strip().lower() for item in value]

    @model_validator(mode="after")
    def _check_environment(self) -> Settings:
        if self.environment == "production":
            if len(self.secret_key) < 32 or self.secret_key.startswith("dev-only"):
                raise ValueError("SECRET_KEY must be set to a strong value in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be enabled in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
