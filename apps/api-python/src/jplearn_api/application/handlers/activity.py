"""Application handlers for Learning Preferences, Daily Activity, Watch History, and History Deletions.

Enforces:
- UC-L16: Setting learning goals, preferred topics, and IANA timezone with OCC revisioning.
- Effective at next local midnight (00:00:00) without retroactive re-aggregation.
- FR-NEG boundaries: metric name is active_watch_seconds / active_ms, zero grammar/CI assumptions.
- Maximum 90 days range for activity query.
- FR-WAT-001: Watch history cursor pagination and isolation before cutoff time.
- Immediate logical hiding of watch history upon deletion request, async physical purging.
- Non-destructive deletion: retains learner_daily_activity, saved_scenes, and personal_collections.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from jplearn_api.application.commands import (
    RequestHistoryDeletionCommand,
    UpdateLearningPreferencesCommand,
)
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import (
    GetDailyActivityQuery,
    GetHistoryDeletionQuery,
    GetLearningPreferencesQuery,
    GetWatchHistoryQuery,
)
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    InvalidDomainStateError,
    RevisionConflictError,
)
from jplearn_api.domain.playback import (
    DEFAULT_TIMEZONE,
    DeletionStatus,
    HistoryDeletionJob,
    LearnerDailyActivity,
    LearningPreferences,
    PlaybackStatus,
    WatchHistoryItemProjection,
)


def calculate_activity_streaks(
    records: list[LearnerDailyActivity],
    terminal_date: str,
    *,
    terminal_is_open_today: bool = False,
) -> tuple[int, int]:
    """Return current and longest goal streaks within the requested date window.

    Multiple policy buckets can share a local date after a timezone change; a
    calendar date counts once when at least one bucket reached its own goal.
    Today's unfinished bucket gets a one-day grace so yesterday's streak stays
    visible until the learner has had the full day to complete today's goal.
    """
    met_dates = {date.fromisoformat(row.date) for row in records if row.goal_met}
    ordered = sorted(met_dates)
    longest = run = 0
    previous = None
    for current in ordered:
        run = run + 1 if previous is not None and current == previous + timedelta(days=1) else 1
        longest = max(longest, run)
        previous = current

    anchor = date.fromisoformat(terminal_date)
    if terminal_is_open_today and anchor not in met_dates:
        anchor -= timedelta(days=1)
    current_streak = 0
    while anchor in met_dates:
        current_streak += 1
        anchor -= timedelta(days=1)
    return current_streak, longest


async def handle_get_learning_preferences(
    query: GetLearningPreferencesQuery,
    uow: AsyncUnitOfWork,
) -> LearningPreferences:
    """Retrieve current learner preferences (goals, timezone, revision)."""
    return await uow.playbacks.get_learning_preferences(query.user_id)


async def handle_update_learning_preferences(
    cmd: UpdateLearningPreferencesCommand,
    uow: AsyncUnitOfWork,
) -> LearningPreferences:
    """Update learner preferences with OCC revision matching and next midnight boundary."""
    async with uow:
        await uow.playbacks.acquire_learner_playback_lock(cmd.user_id, "preferences", "preferences")
        current = await uow.playbacks.get_learning_preferences(cmd.user_id)

        if cmd.expected_revision != current.revision:
            raise RevisionConflictError(f"Revision conflict: expected {cmd.expected_revision}, got {current.revision}")

        if cmd.daily_goal_minutes is not None:
            if cmd.daily_goal_minutes < 0 or cmd.daily_goal_minutes > 120:
                raise InvalidDomainStateError("daily_goal_minutes must be between 0 and 120 (0 means disabled)")

        if cmd.timezone is not None:
            try:
                ZoneInfo(cmd.timezone)
            except Exception:
                raise InvalidDomainStateError(f"Invalid IANA timezone: '{cmd.timezone}'") from None

        now = datetime.now(UTC)
        effective = await uow.playbacks.get_effective_learning_preferences(cmd.user_id, now)
        # Persist the current policy before staging its replacement, including defaults.
        await uow.playbacks.save_preference_version(effective)

        # Compute effective_at: next local midnight (00:00:00) according to current learner timezone
        current_tz_str = effective.timezone or DEFAULT_TIMEZONE
        try:
            current_tz = ZoneInfo(current_tz_str)
        except Exception:
            current_tz = ZoneInfo(DEFAULT_TIMEZONE)

        now = datetime.now(UTC)
        now_local = now.astimezone(current_tz)
        next_day = now_local.date() + timedelta(days=1)
        next_midnight_local = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=current_tz)
        effective_at = next_midnight_local.astimezone(UTC)

        if cmd.daily_goal_minutes is not None:
            current.daily_goal_minutes = cmd.daily_goal_minutes
        if cmd.preferred_topic_ids is not None:
            current.preferred_topic_ids = list(cmd.preferred_topic_ids)
        if cmd.timezone is not None:
            current.timezone = cmd.timezone

        current.revision += 1
        current.effective_at = effective_at
        current.updated_at = now

        if cmd.daily_goal_minutes is not None or cmd.timezone is not None:
            await uow.playbacks.save_preference_version(current)
        await uow.playbacks.save_learning_preferences(current)
        await uow.commit()
        return current


async def handle_get_daily_activity(
    query: GetDailyActivityQuery,
    uow: AsyncUnitOfWork,
) -> list[LearnerDailyActivity]:
    """Retrieve daily activity records for date range (max 90 days)."""
    try:
        d_from = date.fromisoformat(query.from_date)
        d_to = date.fromisoformat(query.to_date)
    except Exception:
        raise InvalidDomainStateError("Dates must be valid ISO format (YYYY-MM-DD)") from None

    if d_from > d_to:
        raise InvalidDomainStateError("from_date must be less than or equal to to_date")

    if (d_to - d_from).days > 90:
        raise InvalidDomainStateError("Date range cannot exceed 90 days")

    return await uow.playbacks.get_daily_activity_range(
        user_id=query.user_id,
        from_date=query.from_date,
        to_date=query.to_date,
    )


async def handle_get_watch_history(
    query: GetWatchHistoryQuery,
    uow: AsyncUnitOfWork,
) -> tuple[list[WatchHistoryItemProjection], str | None]:
    """Retrieve watch history items after latest deletion cutoff with keyset cursor."""
    cutoff_time = await uow.playbacks.get_latest_history_deletion_cutoff(query.user_id)
    limit = max(1, min(query.limit, 100))
    return await uow.playbacks.list_watch_history(
        user_id=query.user_id,
        cutoff_time=cutoff_time,
        cursor=query.cursor,
        limit=limit,
    )


async def handle_request_history_deletion(
    cmd: RequestHistoryDeletionCommand,
    uow: AsyncUnitOfWork,
) -> HistoryDeletionJob:
    """Request watch history deletion, immediately closing active playback and queueing purge."""
    now = datetime.now(UTC)

    async with uow:
        # Acquire lock on playback state to close active session and invalidate leases
        state = await uow.playbacks.acquire_learner_playback_lock(
            user_id=cmd.user_id,
            device_class="system",
            client_instance_id="deletion_worker",
        )

        if state.active_playback_id is not None:
            p = await uow.playbacks.get_playback(state.active_playback_id)
            if p and (p.status == PlaybackStatus.ACTIVE or p.status == "active"):
                p.status = PlaybackStatus.ABANDONED
                p.closed_at = now
                p.updated_at = now
                await uow.playbacks.update_playback(p)

            state.active_playback_id = None
            state.lease_expires_at = now
            state.bump_epoch()
            state.updated_at = now
            await uow.playbacks.update_learner_playback_state(state)

        job = HistoryDeletionJob(
            id=str(uuid4()),
            user_id=cmd.user_id,
            status=DeletionStatus.QUEUED,
            cutoff_time=now,
            records_deleted=0,
            attempts=0,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        created_job = await uow.playbacks.create_history_deletion_job(job)
        await uow.commit()

    return created_job


async def handle_get_history_deletion(
    query: GetHistoryDeletionQuery,
    uow: AsyncUnitOfWork,
) -> HistoryDeletionJob:
    """Check status of a history deletion job."""
    async with uow:
        job = await uow.playbacks.get_history_deletion_job(query.deletion_id)
        if not job or job.user_id != query.user_id:
            raise EntityNotFoundError(f"History deletion job '{query.deletion_id}' not found")
        return job


async def handle_execute_history_deletion_worker(
    uow: AsyncUnitOfWork,
) -> HistoryDeletionJob | None:
    """Worker task: claims next queued history deletion job and purges data."""
    async with uow:
        job = await uow.playbacks.claim_next_history_deletion_job()
        if not job:
            return None

        now = datetime.now(UTC)
        try:
            deleted_count = await uow.playbacks.purge_watch_history_before_cutoff(
                user_id=job.user_id,
                cutoff_time=job.cutoff_time,
            )
            job.status = DeletionStatus.COMPLETED
            job.records_deleted = deleted_count
            job.completed_at = now
            job.updated_at = now
            await uow.playbacks.update_history_deletion_job(job)
        except Exception as ex:
            job.status = DeletionStatus.FAILED
            job.error_message = str(ex)
            job.updated_at = now
            await uow.playbacks.update_history_deletion_job(job)

        await uow.commit()

    return job
