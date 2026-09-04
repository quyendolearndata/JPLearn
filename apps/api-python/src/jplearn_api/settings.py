from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentType = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: EnvironmentType = "local"
    database_url: str
    jwt_secret: str
    api_public_url: str | None = None
    media_signing_secret: str | None = None
    alert_webhook_url: str | None = None
    storage_root: str | None = None
    openapi_ui: bool = False
    port: int = 3002
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_origin_regex: str | None = r"https?://(localhost|127\.0\.0\.1):3000|exp://.*"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    allow_admin_bootstrap: bool = False

    @model_validator(mode="after")
    def validate_configuration(self) -> Settings:
        if len(self.jwt_secret.encode("utf-8")) < 32:
            raise ValueError(
                f"JWT_SECRET must be at least 32 bytes (got {len(self.jwt_secret.encode('utf-8'))} bytes)"
            )

        if self.storage_root is not None:
            storage_path = Path(self.storage_root)
            if not storage_path.is_absolute():
                raise ValueError(
                    f"STORAGE_ROOT must be an absolute path, got '{self.storage_root}'"
                )

        if self.environment in ("staging", "production"):
            if not self.api_public_url or not self.api_public_url.startswith("https://"):
                raise ValueError(
                    f"API_PUBLIC_URL must use HTTPS in {self.environment} environment"
                )
            if not self.media_signing_secret:
                raise ValueError(
                    f"MEDIA_SIGNING_SECRET is required and cannot be empty in {self.environment}"
                )
            if self.media_signing_secret == self.jwt_secret:
                raise ValueError(
                    f"MEDIA_SIGNING_SECRET must be distinct from JWT_SECRET in {self.environment}"
                )

        return self


def get_settings() -> Settings:
    return Settings()

