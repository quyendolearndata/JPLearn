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
    cors_origin_regex: str | None = None
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    allow_admin_bootstrap: bool = False

    @model_validator(mode="after")
    def validate_configuration(self) -> Settings:
        from urllib.parse import urlparse

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

        if self.environment in ("local", "test"):
            if self.cors_origin_regex is None:
                self.cors_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?|exp://.*"

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

            # Reject default localhost origins in staging/production
            default_localhost_origins = {"http://localhost:3000", "http://127.0.0.1:3000"}
            if set(self.cors_origins) == default_localhost_origins:
                raise ValueError(
                    f"Explicit HTTPS CORS_ORIGINS required in {self.environment} (cannot inherit default localhost origins)"
                )

            if not self.cors_origins or any(o.strip() in ("*", "null") for o in self.cors_origins):
                raise ValueError(
                    f"CORS_ORIGINS cannot be empty, null, or contain wildcard '*' in {self.environment}"
                )

            for origin in self.cors_origins:
                parsed = urlparse(origin)
                if parsed.scheme != "https":
                    raise ValueError(
                        f"CORS_ORIGINS entries must use HTTPS in {self.environment}, got '{origin}'"
                    )
                if not parsed.netloc:
                    raise ValueError(
                        f"Invalid CORS origin netloc in {self.environment}: '{origin}'"
                    )
                if parsed.path not in ("", "/"):
                    raise ValueError(
                        f"CORS origin must not include a path in {self.environment}: '{origin}'"
                    )
                if parsed.params or parsed.query or parsed.fragment:
                    raise ValueError(
                        f"CORS origin must not include query or fragment in {self.environment}: '{origin}'"
                    )
                if "@" in parsed.netloc:
                    raise ValueError(
                        f"CORS origin must not contain user credentials in {self.environment}: '{origin}'"
                    )

            if self.cors_origin_regex is not None:
                # Reject permissive regexes in staging/production (must not match exp:// or localhost)
                broad_tokens = [".*", ".+", "exp://", "localhost", "127.0.0.1", "http://"]
                if any(tok in self.cors_origin_regex for tok in broad_tokens):
                    raise ValueError(
                        f"Broad or unapproved CORS_ORIGIN_REGEX rejected in {self.environment}: '{self.cors_origin_regex}'"
                    )

            if "dev-secret" in self.jwt_secret.lower() or "change-me" in self.jwt_secret.lower():
                raise ValueError(
                    f"Insecure JWT_SECRET detected in {self.environment} environment"
                )
            if self.allow_admin_bootstrap and self.environment == "production":
                raise ValueError("ALLOW_ADMIN_BOOTSTRAP cannot be enabled in production")

        return self


def get_settings() -> Settings:
    return Settings()

