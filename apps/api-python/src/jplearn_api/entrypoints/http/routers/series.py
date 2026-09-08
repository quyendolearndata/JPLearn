from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.handlers.series import (
    handle_create_series,
    handle_get_learner_series,
    handle_get_staff_series,
    handle_list_learner_series,
    handle_list_staff_series,
    handle_publish_series,
    handle_return_series_to_draft,
    handle_submit_series_qa,
    handle_unpublish_series,
    handle_update_series_items,
    handle_update_series_metadata,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.domain.series import Series
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.schemas import (
    SeriesActionBody,
    SeriesCreateBody,
    SeriesItemStaffPublic,
    SeriesItemsUpdateBody,
    SeriesLearnerClipPublic,
    SeriesLearnerPublic,
    SeriesLearnerSummary,
    SeriesPatchBody,
    SeriesReturnToDraftBody,
    SeriesStaffPublic,
    SeriesStaffSummary,
)
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(tags=["Series"])


def _to_staff_public(series: Series) -> SeriesStaffPublic:
    return SeriesStaffPublic(
        id=series.id,
        title=series.title,
        description=series.description,
        ci_level=series.ci_level,
        topic_id=series.topic_id,
        status=series.status,  # type: ignore[arg-type]
        revision=series.revision,
        items=[
            SeriesItemStaffPublic(
                catalog_item_id=it.catalog_item_id,
                position=it.position,
            )
            for it in series.items
        ],
        created_at=series.created_at.isoformat(),
        updated_at=series.updated_at.isoformat(),
    )


@router.post(
    "/staff/series",
    response_model=SeriesStaffPublic,
    status_code=status.HTTP_201_CREATED,
    operation_id="createSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        400: {"description": "Validation error or invalid topic"},
        403: {"description": "Staff only"},
    },
)
async def create_series(
    body: SeriesCreateBody,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_create_series(
            uow=uow,
            title=body.title,
            description=body.description,
            ci_level=body.ci_level,
            topic_id=body.topic_id,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.get(
    "/staff/series",
    response_model=list[SeriesStaffSummary],
    operation_id="listStaffSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        403: {"description": "Staff only"},
    },
)
async def list_staff_series(
    status_filter: str | None = Query(default=None, alias="status"),
    ci_level: str | None = Query(default=None),
    topic_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> list[SeriesStaffSummary]:
    uow = create_uow(session)
    try:
        series_list = await handle_list_staff_series(
            uow=uow,
            status=status_filter,
            ci_level=ci_level,
            topic_id=topic_id,
            offset=offset,
            limit=limit,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return [
        SeriesStaffSummary(
            id=s.id,
            title=s.title,
            description=s.description,
            ci_level=s.ci_level,
            topic_id=s.topic_id,
            status=s.status,  # type: ignore[arg-type]
            revision=s.revision,
            item_count=len(s.items),
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in series_list
    ]


@router.get(
    "/staff/series/{id}",
    response_model=SeriesStaffPublic,
    operation_id="getStaffSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        403: {"description": "Staff only"},
        404: {"description": "Series not found"},
    },
)
async def get_staff_series(
    id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_get_staff_series(uow, id)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.patch(
    "/staff/series/{id}",
    response_model=SeriesStaffPublic,
    operation_id="updateStaffSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        400: {"description": "Validation error"},
        403: {"description": "Staff only"},
        404: {"description": "Series not found"},
        409: {"description": "Revision conflict"},
    },
)
async def update_staff_series(
    id: UUIDPath,
    body: SeriesPatchBody,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_update_series_metadata(
            uow=uow,
            series_id=id,
            expected_revision=body.expected_revision,
            title=body.title,
            description=body.description,
            ci_level=body.ci_level,
            topic_id=body.topic_id,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.put(
    "/staff/series/{id}/items",
    response_model=SeriesStaffPublic,
    operation_id="updateStaffSeriesItems",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        400: {"description": "Validation error or missing items"},
        403: {"description": "Staff only"},
        404: {"description": "Series not found"},
        409: {"description": "Revision conflict"},
    },
)
async def update_staff_series_items(
    id: UUIDPath,
    body: SeriesItemsUpdateBody,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_update_series_items(
            uow=uow,
            series_id=id,
            expected_revision=body.expected_revision,
            item_ids=body.item_ids,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.post(
    "/staff/series/{id}/submit-qa",
    response_model=SeriesStaffPublic,
    operation_id="submitStaffSeriesQa",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        400: {"description": "Validation error or series has no items"},
        403: {"description": "Staff only"},
        404: {"description": "Series not found"},
        409: {"description": "Revision conflict"},
    },
)
async def submit_staff_series_qa(
    id: UUIDPath,
    body: SeriesActionBody,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_submit_series_qa(
            uow=uow,
            series_id=id,
            expected_revision=body.expected_revision,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.post(
    "/staff/series/{id}/return-to-draft",
    response_model=SeriesStaffPublic,
    operation_id="returnStaffSeriesToDraft",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        400: {"description": "Validation error"},
        403: {"description": "Admin only"},
        404: {"description": "Series not found"},
        409: {"description": "Revision conflict"},
    },
)
async def return_staff_series_to_draft(
    id: UUIDPath,
    body: SeriesReturnToDraftBody,
    session: AsyncSession = Depends(get_session),
    _admin: UserDTO = Depends(require_roles("admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_return_series_to_draft(
            uow=uow,
            series_id=id,
            expected_revision=body.expected_revision,
            reason=body.reason,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.post(
    "/staff/series/{id}/publish",
    response_model=SeriesStaffPublic,
    operation_id="publishStaffSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        400: {"description": "Validation error or items unpublished"},
        403: {"description": "Admin only"},
        404: {"description": "Series not found"},
        409: {"description": "Revision conflict"},
    },
)
async def publish_staff_series(
    id: UUIDPath,
    body: SeriesActionBody,
    session: AsyncSession = Depends(get_session),
    _admin: UserDTO = Depends(require_roles("admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_publish_series(
            uow=uow,
            series_id=id,
            expected_revision=body.expected_revision,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.post(
    "/staff/series/{id}/unpublish",
    response_model=SeriesStaffPublic,
    operation_id="unpublishStaffSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001"]},
    responses={
        400: {"description": "Validation error"},
        403: {"description": "Admin only"},
        404: {"description": "Series not found"},
        409: {"description": "Revision conflict"},
    },
)
async def unpublish_staff_series(
    id: UUIDPath,
    body: SeriesActionBody,
    session: AsyncSession = Depends(get_session),
    _admin: UserDTO = Depends(require_roles("admin")),
) -> SeriesStaffPublic:
    uow = create_uow(session)
    try:
        series = await handle_unpublish_series(
            uow=uow,
            series_id=id,
            expected_revision=body.expected_revision,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return _to_staff_public(series)


@router.get(
    "/series",
    response_model=list[SeriesLearnerSummary],
    operation_id="listLearnerSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001", "FR-LRN-001"]},
    responses={
        401: {"description": "Authentication required"},
    },
)
async def list_learner_series(
    ci_level: str | None = Query(default=None),
    topic_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_user),
) -> list[SeriesLearnerSummary]:
    uow = create_uow(session)
    try:
        series_tuples = await handle_list_learner_series(
            uow=uow,
            ci_level=ci_level,
            topic_id=topic_id,
            offset=offset,
            limit=limit,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return [
        SeriesLearnerSummary(
            id=s.id,
            title=s.title,
            description=s.description,
            ci_level=s.ci_level,
            topic_id=s.topic_id,
            available_item_count=count,
        )
        for s, count in series_tuples
    ]


@router.get(
    "/series/{id}",
    response_model=SeriesLearnerPublic,
    operation_id="getLearnerSeries",
    openapi_extra={"x-jplearn-fr": ["FR-SER-001", "FR-LRN-001"]},
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Series not found or has no available clips"},
    },
)
async def get_learner_series(
    id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_user),
) -> SeriesLearnerPublic:
    uow = create_uow(session)
    try:
        series, clips = await handle_get_learner_series(uow, id)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return SeriesLearnerPublic(
        id=series.id,
        title=series.title,
        description=series.description,
        ci_level=series.ci_level,
        topic_id=series.topic_id,
        items=[
            SeriesLearnerClipPublic(
                catalog_item_id=c["catalog_item_id"],
                position=c["position"],
                topic_id=c["topic_id"],
                ci_level=c["ci_level"],
                duration_seconds=c["duration_seconds"],
            )
            for c in clips
        ],
    )
