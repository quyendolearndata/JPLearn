from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict


class HealthBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: Literal[True]


router = APIRouter(tags=["Observability"])


@router.get(
    "/health",
    response_model=HealthBody,
    operation_id="health",
    openapi_extra={"x-jplearn-fr": ["NFR-OBS-001"]},
)
def health() -> HealthBody:
    return HealthBody(ok=True)
