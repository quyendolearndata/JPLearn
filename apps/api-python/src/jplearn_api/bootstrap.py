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
from jplearn_api.adapters.storage.local import LocalFilesystemStorage, StoragePort
from jplearn_api.settings import Settings, get_settings


@dataclass(frozen=True)
class AppContainer:
    """Composition root container holding runtime adapters and immutable settings."""

    settings: Settings
    storage: StoragePort
    password_hasher: Argon2PasswordHasher
    token_service: JwtTokenService


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
    )


def create_uow(session: Any) -> SqlAlchemyUnitOfWork:
    """Factory creating a new Unit of Work for a write transaction."""
    return SqlAlchemyUnitOfWork(session)


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
