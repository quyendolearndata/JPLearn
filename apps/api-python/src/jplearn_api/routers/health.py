import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.deps import get_session, get_storage
from jplearn_api.storage import StoragePort


class HealthBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: Literal[True]


class ReadyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    database: Literal["up", "down"]
    storage: Literal["up", "down"]


router = APIRouter(tags=["Observability"])


@router.get(
    "/health",
    response_model=HealthBody,
    operation_id="health",
    openapi_extra={"x-jplearn-fr": ["NFR-OBS-001"]},
)
def health() -> HealthBody:
    return HealthBody(ok=True)


@router.get(
    "/ready",
    response_model=ReadyBody,
    operation_id="ready",
    openapi_extra={"x-jplearn-fr": ["NFR-OBS-001"]},
    responses={
        200: {"description": "Service dependencies are healthy", "model": ReadyBody},
        503: {"description": "One or more service dependencies are unhealthy", "model": ReadyBody},
    },
)
async def ready(
    response: Response,
    session: AsyncSession = Depends(get_session),
    storage: StoragePort = Depends(get_storage),
) -> ReadyBody:
    async def _check_db() -> bool:
        try:
            await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def _check_storage() -> bool:
        try:
            probe_ok, _msg = await storage.check_ready()
            return probe_ok
        except Exception:
            return False

    try:
        results = await asyncio.wait_for(
            asyncio.gather(_check_db(), _check_storage(), return_exceptions=True),
            timeout=2.0,
        )
        db_res, storage_res = results
        db_ok = bool(db_res) if not isinstance(db_res, Exception) else False
        storage_ok = bool(storage_res) if not isinstance(storage_res, Exception) else False
    except Exception:
        db_ok = False
        storage_ok = False

    is_healthy = db_ok and storage_ok
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyBody(
        ok=is_healthy,
        database="up" if db_ok else "down",
        storage="up" if storage_ok else "down",
    )

