from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    api_public_url: str | None = None
    media_signing_secret: str | None = None
    alert_webhook_url: str | None = None
    storage_root: str | None = None
    openapi_ui: bool = False
    port: int = 3002


def get_settings() -> Settings:
    return Settings()
