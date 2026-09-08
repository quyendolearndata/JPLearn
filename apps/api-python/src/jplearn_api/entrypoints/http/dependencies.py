from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.ports.security import MediaUrlSigner
from jplearn_api.application.ports.unit_of_work import UnitOfWorkFactory
from jplearn_api.bootstrap import create_media_signer, create_uow_factory
from jplearn_api.adapters.storage.local import StoragePort

UUIDPath = Annotated[str, Path(json_schema_extra={"format": "uuid"})]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.sessionmaker
    async with factory() as session:
        yield session


def get_uow_factory(request: Request) -> UnitOfWorkFactory:
    return create_uow_factory(request.app.state.sessionmaker)


def get_storage(request: Request) -> StoragePort:
    return request.app.state.storage


def get_media_signer(request: Request) -> MediaUrlSigner:
    signer = getattr(request.app.state, "media_signer", None)
    if signer is None:
        signer = create_media_signer(request.app.state.settings)
        request.app.state.media_signer = signer
    return signer


def get_app_settings(request: Request):
    return request.app.state.settings


import functools


@functools.lru_cache(maxsize=None)
def require_capability(flag_name: str):
    """Dependency that ensures the runtime capability switch is enabled, else 403 Forbidden."""
    from fastapi import HTTPException

    def _checker(request: Request) -> None:
        settings = get_app_settings(request)
        if not getattr(settings, flag_name, False):
            raise HTTPException(
                status_code=403,
                detail=f"Capability '{flag_name}' is currently disabled",
            )

    return _checker
