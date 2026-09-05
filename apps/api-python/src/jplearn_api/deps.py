from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.storage import StoragePort

UUIDPath = Annotated[str, Path(json_schema_extra={"format": "uuid"})]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.sessionmaker
    async with factory() as session:
        yield session


def get_storage(request: Request) -> StoragePort:
    return request.app.state.storage


