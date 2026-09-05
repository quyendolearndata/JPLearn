"""Application bootstrap and dependency container (Composition Root)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jplearn_api.adapters.persistence.catalog_repository import (
    SqlAlchemyCatalogQueryAdapter,
    SqlAlchemyCatalogRepository,
)
from jplearn_api.adapters.persistence.flags_repository import SqlAlchemyFlagsRepository
from jplearn_api.adapters.persistence.learning_repository import SqlAlchemyLearningRepository
from jplearn_api.adapters.persistence.media_repository import SqlAlchemyMediaRepository
from jplearn_api.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWork
from jplearn_api.adapters.persistence.user_repository import SqlAlchemyUserRepository
from jplearn_api.adapters.security.argon2 import Argon2PasswordHasher
from jplearn_api.adapters.security.jwt import JwtTokenService
from jplearn_api.adapters.security.media_signer import HmacMediaUrlSigner
from jplearn_api.application.ports.security import MediaUrlSigner, PasswordHasher, TokenService
from jplearn_api.adapters.storage.local import LocalFilesystemStorage, StoragePort
from jplearn_api.settings import Settings, get_settings


@dataclass(frozen=True)
class AppContainer:
    """Composition root container holding runtime adapters and immutable settings."""

    settings: Settings
    storage: StoragePort
    password_hasher: Argon2PasswordHasher
    token_service: JwtTokenService
    media_signer: MediaUrlSigner


def create_password_hasher() -> PasswordHasher:
    """Factory creating a password hasher adapter."""
    return Argon2PasswordHasher()


def create_token_service() -> TokenService:
    """Factory creating a token service adapter."""
    return JwtTokenService()


def create_media_signer(settings: Settings | None = None) -> HmacMediaUrlSigner:
    """Factory creating a Media URL signer adapter."""
    resolved_settings = settings or get_settings()
    base_url = resolved_settings.api_public_url or "http://localhost:3001"
    secret = resolved_settings.media_signing_secret or resolved_settings.jwt_secret or "default-secret"
    return HmacMediaUrlSigner(base_url=base_url, secret=secret)


def create_app_container(
    settings: Settings | None = None,
    storage: StoragePort | None = None,
) -> AppContainer:
    """Bootstrap application container with explicit dependencies."""
    resolved_settings = settings or get_settings()
    resolved_storage = storage or LocalFilesystemStorage(
        resolved_settings.storage_root or (Path.cwd() / "storage")
    )
    return AppContainer(
        settings=resolved_settings,
        storage=resolved_storage,
        password_hasher=Argon2PasswordHasher(),
        token_service=JwtTokenService(),
        media_signer=create_media_signer(resolved_settings),
    )


def create_uow(session: Any) -> SqlAlchemyUnitOfWork:
    """Factory creating a new Unit of Work for a write transaction."""
    return SqlAlchemyUnitOfWork(session)


def create_uow_factory(sessionmaker: Any) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Factory creating a new Unit of Work factory for write transactions."""
    return lambda: SqlAlchemyUnitOfWork(sessionmaker)


def create_user_repository(session: Any) -> SqlAlchemyUserRepository:
    """Factory creating a User repository adapter."""
    return SqlAlchemyUserRepository(session)


def create_catalog_repository(session: Any) -> SqlAlchemyCatalogRepository:
    """Factory creating a Catalog repository adapter."""
    return SqlAlchemyCatalogRepository(session)


def create_catalog_query(session: Any, settings: Settings | None = None) -> SqlAlchemyCatalogQueryAdapter:
    """Factory creating a Catalog query adapter."""
    return SqlAlchemyCatalogQueryAdapter(session, settings)


def create_learning_repository(session: Any) -> SqlAlchemyLearningRepository:
    """Factory creating a Learning repository adapter."""
    return SqlAlchemyLearningRepository(session)


def create_media_repository(session: Any) -> SqlAlchemyMediaRepository:
    """Factory creating a Media repository adapter."""
    return SqlAlchemyMediaRepository(session)


def create_flags_repository(session: Any) -> SqlAlchemyFlagsRepository:
    """Factory creating a Flags repository adapter."""
    return SqlAlchemyFlagsRepository(session)
