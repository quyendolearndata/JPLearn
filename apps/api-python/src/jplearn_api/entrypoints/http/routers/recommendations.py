"""HTTP router for learner content recommendations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.handlers.recommendations import handle_get_recommendations
from jplearn_api.application.queries import GetRecommendationsQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import get_session
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.schemas import (
    RecommendationsResponsePublic,
    RecommendedItemPublic,
)
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(prefix="/me", tags=["Recommendations"])


@router.get(
    "/recommendations",
    response_model=RecommendationsResponsePublic,
    operation_id="getRecommendations",
    openapi_extra={"x-jplearn-fr": ["UC-L16", "UC-L17", "FR-WAT-001", "FR-NEG"]},
    responses={
        200: {
            "description": "Recommended items retrieved successfully",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RecommendationsResponsePublic"}}},
        },
        401: {"description": "Authentication required"},
    },
)
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of recommendations to return"),
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> RecommendationsResponsePublic:
    uow = create_uow(session)
    query = GetRecommendationsQuery(user_id=user.id, limit=limit)
    try:
        items, strategy_version = await handle_get_recommendations(query, uow)
        items_public = [
            RecommendedItemPublic(
                catalog_item_id=it.catalog_item_id,
                media_type=it.media_type,
                topic_id=it.topic_id,
                duration_seconds=it.duration_seconds,
                ci_level=it.ci_level,
                reason=it.reason.value if hasattr(it.reason, "value") else str(it.reason),
                title_jp=it.title_jp,
                series_id=it.series_id,
                series_title=it.series_title,
            )
            for it in items
        ]
        return RecommendationsResponsePublic(
            items=items_public,
            strategy_version=strategy_version,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from None
