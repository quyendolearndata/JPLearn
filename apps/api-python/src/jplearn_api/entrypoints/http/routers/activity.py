"""HTTP router for learner preferences, daily activity, watch history, and history deletions."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    RequestHistoryDeletionCommand,
    UpdateLearningPreferencesCommand,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.application.handlers.activity import (
    handle_get_daily_activity,
    handle_get_history_deletion,
    handle_get_learning_preferences,
    handle_get_watch_history,
    handle_request_history_deletion,
    handle_update_learning_preferences,
    calculate_activity_streaks,
)
from jplearn_api.application.queries import (
    GetDailyActivityQuery,
    GetHistoryDeletionQuery,
    GetLearningPreferencesQuery,
    GetWatchHistoryQuery,
)
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.schemas import (
    DailyActivityItemPublic,
    HistoryDeletionCreatedPublic,
    HistoryDeletionStatusPublic,
    LearnerActivityResponsePublic,
    LearningPreferencesPublic,
    LearningPolicyPublic,
    UpdateLearningPreferencesBody,
    WatchHistoryItemPublic,
    WatchHistoryResponsePublic,
)
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(prefix="/me", tags=["Activity & Preferences"])


@router.get(
    "/learning-preferences",
    response_model=LearningPreferencesPublic,
    operation_id="getLearningPreferences",
    openapi_extra={"x-jplearn-fr": ["UC-L16"]},
    responses={
        200: {
            "description": "Learner preferences retrieved successfully",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/LearningPreferencesPublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
    },
)
async def get_learning_preferences(
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> LearningPreferencesPublic:
    uow = create_uow(session)
    query = GetLearningPreferencesQuery(user_id=user.id)
    try:
        pref = await handle_get_learning_preferences(query, uow)
        current = await uow.playbacks.get_effective_learning_preferences(user.id, datetime.now(timezone.utc))
        pending_at = pref.effective_at.replace(tzinfo=timezone.utc) if pref.effective_at.tzinfo is None else pref.effective_at
        return LearningPreferencesPublic(
            current_policy=LearningPolicyPublic(daily_goal_minutes=current.daily_goal_minutes, timezone=current.timezone, effective_at=current.effective_at),
            pending_policy=LearningPolicyPublic(daily_goal_minutes=pref.daily_goal_minutes, timezone=pref.timezone, effective_at=pref.effective_at) if pending_at > datetime.now(timezone.utc) and (pref.daily_goal_minutes, pref.timezone) != (current.daily_goal_minutes, current.timezone) else None,
            daily_goal_minutes=pref.daily_goal_minutes,
            preferred_topic_ids=pref.preferred_topic_ids,
            timezone=pref.timezone,
            revision=pref.revision,
            effective_at=pref.effective_at,
            created_at=pref.created_at,
            updated_at=pref.updated_at,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc)


@router.put(
    "/learning-preferences",
    response_model=LearningPreferencesPublic,
    operation_id="updateLearningPreferences",
    openapi_extra={"x-jplearn-fr": ["UC-L16"]},
    responses={
        200: {
            "description": "Learner preferences updated successfully",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/LearningPreferencesPublic"}
                }
            },
        },
        400: {"description": "Invalid goal or timezone"},
        401: {"description": "Authentication required"},
        409: {"description": "Revision mismatch (optimistic concurrency control)"},
    },
)
async def update_learning_preferences(
    payload: UpdateLearningPreferencesBody,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> LearningPreferencesPublic:
    uow = create_uow(session)
    cmd = UpdateLearningPreferencesCommand(
        user_id=user.id,
        expected_revision=payload.expected_revision,
        daily_goal_minutes=payload.daily_goal_minutes,
        preferred_topic_ids=payload.preferred_topic_ids,
        timezone=payload.timezone,
    )
    try:
        pref = await handle_update_learning_preferences(cmd, uow)
        await session.commit()
        current = await uow.playbacks.get_effective_learning_preferences(user.id, datetime.now(timezone.utc))
        pending_at = pref.effective_at.replace(tzinfo=timezone.utc) if pref.effective_at.tzinfo is None else pref.effective_at
        return LearningPreferencesPublic(
            current_policy=LearningPolicyPublic(daily_goal_minutes=current.daily_goal_minutes, timezone=current.timezone, effective_at=current.effective_at),
            pending_policy=LearningPolicyPublic(daily_goal_minutes=pref.daily_goal_minutes, timezone=pref.timezone, effective_at=pref.effective_at) if pending_at > datetime.now(timezone.utc) and (pref.daily_goal_minutes, pref.timezone) != (current.daily_goal_minutes, current.timezone) else None,
            daily_goal_minutes=pref.daily_goal_minutes,
            preferred_topic_ids=pref.preferred_topic_ids,
            timezone=pref.timezone,
            revision=pref.revision,
            effective_at=pref.effective_at,
            created_at=pref.created_at,
            updated_at=pref.updated_at,
        )
    except DomainError as exc:
        await session.rollback()
        raise map_domain_error_to_http(exc)


@router.get(
    "/activity",
    response_model=LearnerActivityResponsePublic,
    operation_id="getLearnerActivity",
    openapi_extra={"x-jplearn-fr": ["UC-L16", "FR-NEG"]},
    responses={
        200: {
            "description": "Daily activity retrieved successfully",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/LearnerActivityResponsePublic"}
                }
            },
        },
        400: {"description": "Invalid date range or exceeding 90 days limit"},
        401: {"description": "Authentication required"},
    },
)
async def get_learner_activity(
    from_date: str = Query(..., alias="from", description="Start date in YYYY-MM-DD format"),
    to_date: str = Query(..., alias="to", description="End date in YYYY-MM-DD format"),
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> LearnerActivityResponsePublic:
    uow = create_uow(session)
    query = GetDailyActivityQuery(
        user_id=user.id,
        from_date=from_date,
        to_date=to_date,
    )
    try:
        records = await handle_get_daily_activity(query, uow)
        items_public = [
            DailyActivityItemPublic(
                date=act.date,
                timezone=act.timezone,
                policy_revision=act.policy_revision,
                active_ms=act.active_ms,
                active_watch_seconds=act.active_ms // 1000,
                goal_minutes=act.goal_minutes,
                goal_seconds=act.goal_minutes * 60,
                goal_met=act.goal_met,
                updated_at=act.updated_at,
            )
            for act in records
        ]
        total_seconds = sum(item.active_watch_seconds for item in items_public)
        days_met = len({item.date for item in items_public if item.goal_met})
        effective = await uow.playbacks.get_effective_learning_preferences(user.id, datetime.now(timezone.utc))
        today = datetime.now(timezone.utc).astimezone(ZoneInfo(effective.timezone)).date().isoformat()
        current_streak, longest_streak = calculate_activity_streaks(
            records, to_date, terminal_is_open_today=(to_date == today),
        )
        return LearnerActivityResponsePublic(
            items=items_public,
            total_active_watch_seconds=total_seconds,
            days_goal_met=days_met,
            current_streak_days=current_streak,
            longest_streak_days=longest_streak,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc)


@router.get(
    "/watch-history",
    response_model=WatchHistoryResponsePublic,
    operation_id="getWatchHistory",
    openapi_extra={"x-jplearn-fr": ["FR-WAT-001"]},
    responses={
        200: {
            "description": "Watch history list with pagination cursor",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/WatchHistoryResponsePublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
    },
)
async def get_watch_history(
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
    limit: int = Query(50, ge=1, le=100),
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> WatchHistoryResponsePublic:
    uow = create_uow(session)
    query = GetWatchHistoryQuery(
        user_id=user.id,
        cursor=cursor,
        limit=limit,
    )
    try:
        items, next_cursor = await handle_get_watch_history(query, uow)
        items_public = [
            WatchHistoryItemPublic(
                playback_id=it.playback_id,
                catalog_item_id=it.catalog_item_id,
                title_jp=it.title_jp,
                item_type=it.item_type,
                topic_id=it.topic_id,
                duration_seconds=it.duration_seconds,
                status=it.status,
                last_position_ms=it.last_position_ms,
                total_active_ms=it.total_active_ms,
                content_version_id=it.content_version_id,
                created_at=it.created_at,
                updated_at=it.updated_at,
            )
            for it in items
        ]
        return WatchHistoryResponsePublic(
            items=items_public,
            next_cursor=next_cursor,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc)


@router.delete(
    "/watch-history",
    response_model=HistoryDeletionCreatedPublic,
    operation_id="requestWatchHistoryDeletion",
    openapi_extra={"x-jplearn-fr": ["FR-WAT-001"]},
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": "Watch history deletion accepted and queued",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HistoryDeletionCreatedPublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
    },
)
async def delete_watch_history(
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> HistoryDeletionCreatedPublic:
    uow = create_uow(session)
    cmd = RequestHistoryDeletionCommand(user_id=user.id)
    try:
        job = await handle_request_history_deletion(cmd, uow)
        await session.commit()
        return HistoryDeletionCreatedPublic(
            deletion_id=job.id,
            cutoff_time=job.cutoff_time,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            message="Watch history deletion accepted and queued for processing",
        )
    except DomainError as exc:
        await session.rollback()
        raise map_domain_error_to_http(exc)


@router.get(
    "/history-deletions/{deletion_id}",
    response_model=HistoryDeletionStatusPublic,
    operation_id="getHistoryDeletionStatus",
    openapi_extra={"x-jplearn-fr": ["FR-WAT-001"]},
    responses={
        200: {
            "description": "History deletion status retrieved successfully",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HistoryDeletionStatusPublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
        404: {"description": "History deletion job not found"},
    },
)
async def get_history_deletion_status(
    deletion_id: UUIDPath,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> HistoryDeletionStatusPublic:
    uow = create_uow(session)
    query = GetHistoryDeletionQuery(
        user_id=user.id,
        deletion_id=deletion_id,
    )
    try:
        job = await handle_get_history_deletion(query, uow)
        return HistoryDeletionStatusPublic(
            deletion_id=job.id,
            user_id=job.user_id,
            cutoff_time=job.cutoff_time,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            records_deleted=job.records_deleted,
            attempts=job.attempts,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc)
