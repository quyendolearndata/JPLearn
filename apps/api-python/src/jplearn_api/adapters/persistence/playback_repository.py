"""SQLAlchemy implementation of PlaybackRepository."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy import desc, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import (
    CatalogItem as OrmCatalogItem,
    HistoryDeletion as OrmHistoryDeletion,
    LearnerDailyActivity as OrmLearnerDailyActivity,
    LearnerPlaybackState as OrmLearnerPlaybackState,
    LearningPreferences as OrmLearningPreferences,
    Playback as OrmPlayback,
    PlaybackCheckpoint as OrmPlaybackCheckpoint,
    PlaybackReceipt as OrmPlaybackReceipt,
)
from jplearn_api.domain.playback import (
    DeletionStatus,
    HistoryDeletionJob,
    LearnerDailyActivity,
    LearnerPlaybackState,
    LearningPreferences,
    PlaybackCheckpoint,
    PlaybackReceipt,
    PlaybackSession,
    PlaybackStatus,
    WatchHistoryItemProjection,
)


def _strip_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


class SqlAlchemyPlaybackRepository:
    """SQLAlchemy adapter for PlaybackRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def acquire_learner_playback_lock(
        self,
        user_id: str,
        device_class: str,
        client_instance_id: str,
    ) -> LearnerPlaybackState:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            select(OrmLearnerPlaybackState)
            .where(OrmLearnerPlaybackState.user_id == user_id)
            .with_for_update()
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if orm is None:
            # First use only. Established playback and preference writers take
            # the common one-query lock path above.
            await self._session.execute(
                text(
                    """
                    INSERT INTO learner_playback_state (
                        user_id, active_playback_id, current_epoch, lease_expires_at, device_class, client_instance_id, updated_at
                    )
                    VALUES (
                        :user_id, NULL, 1, :lease_expires_at, :device_class, :client_instance_id, :updated_at
                    )
                    ON CONFLICT (user_id) DO NOTHING
                    """
                ),
                {
                    "user_id": user_id,
                    "lease_expires_at": now,
                    "device_class": device_class,
                    "client_instance_id": client_instance_id,
                    "updated_at": now,
                },
            )
            orm = (await self._session.execute(stmt)).scalar_one()
        return LearnerPlaybackState(
            user_id=orm.user_id,
            active_playback_id=orm.active_playback_id,
            current_epoch=orm.current_epoch,
            lease_expires_at=orm.lease_expires_at,
            device_class=orm.device_class,
            client_instance_id=orm.client_instance_id,
            updated_at=orm.updated_at,
        )

    async def update_learner_playback_state(self, state: LearnerPlaybackState) -> None:
        await self._session.execute(update(OrmLearnerPlaybackState).where(
            OrmLearnerPlaybackState.user_id == state.user_id).values(
            active_playback_id=state.active_playback_id, current_epoch=state.current_epoch,
            lease_expires_at=_strip_tz(state.lease_expires_at), device_class=state.device_class,
            client_instance_id=state.client_instance_id, updated_at=_strip_tz(state.updated_at)))

    async def get_playback(self, playback_id: str) -> PlaybackSession | None:
        stmt = select(OrmPlayback).where(OrmPlayback.id == playback_id).execution_options(populate_existing=True)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return PlaybackSession(
            id=orm.id,
            user_id=orm.user_id,
            catalog_item_id=orm.catalog_item_id,
            content_version_id=orm.content_version_id,
            epoch=orm.epoch,
            device_class=orm.device_class,
            client_instance_id=orm.client_instance_id,
            status=PlaybackStatus(orm.status),
            last_seq=orm.last_seq,
            total_active_ms=orm.total_active_ms,
            last_position_ms=orm.last_position_ms,
            last_server_time=orm.last_server_time,
            last_client_cumulative_ms=orm.last_client_cumulative_ms,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            closed_at=orm.closed_at,
        )

    async def create_playback(self, session: PlaybackSession) -> PlaybackSession:
        orm = OrmPlayback(
            id=session.id,
            user_id=session.user_id,
            catalog_item_id=session.catalog_item_id,
            content_version_id=session.content_version_id,
            epoch=session.epoch,
            device_class=session.device_class,
            client_instance_id=session.client_instance_id,
            status=session.status.value if hasattr(session.status, "value") else str(session.status),
            last_seq=session.last_seq,
            total_active_ms=session.total_active_ms,
            last_position_ms=session.last_position_ms,
            last_server_time=_strip_tz(session.last_server_time),
            last_client_cumulative_ms=session.last_client_cumulative_ms,
            created_at=_strip_tz(session.created_at),
            updated_at=_strip_tz(session.updated_at),
            closed_at=_strip_tz(session.closed_at),
        )
        self._session.add(orm)
        await self._session.flush()
        return session

    async def update_playback(self, session: PlaybackSession) -> None:
        await self._session.execute(update(OrmPlayback).where(OrmPlayback.id == session.id).values(
            status=session.status.value, last_seq=session.last_seq, total_active_ms=session.total_active_ms,
            last_position_ms=session.last_position_ms, last_server_time=_strip_tz(session.last_server_time),
            last_client_cumulative_ms=session.last_client_cumulative_ms,
            updated_at=_strip_tz(session.updated_at), closed_at=_strip_tz(session.closed_at)))

    async def get_receipt(self, playback_id: str, seq: int) -> PlaybackReceipt | None:
        stmt = select(OrmPlaybackReceipt).where(
            OrmPlaybackReceipt.playback_id == playback_id,
            OrmPlaybackReceipt.seq == seq,
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return PlaybackReceipt(
            playback_id=orm.playback_id,
            seq=orm.seq,
            request_hash=orm.request_hash,
            accepted_delta_ms=orm.accepted_delta_ms,
            cumulative_active_ms=orm.cumulative_active_ms,
            response_payload=orm.response_payload,
            created_at=orm.created_at,
        )

    async def save_receipt(self, receipt: PlaybackReceipt) -> None:
        orm = OrmPlaybackReceipt(
            playback_id=receipt.playback_id,
            seq=receipt.seq,
            request_hash=receipt.request_hash,
            accepted_delta_ms=receipt.accepted_delta_ms,
            cumulative_active_ms=receipt.cumulative_active_ms,
            response_payload=receipt.response_payload,
            created_at=_strip_tz(receipt.created_at),
        )
        self._session.add(orm)
        await self._session.flush()

    async def get_checkpoint(self, user_id: str, catalog_item_id: str) -> PlaybackCheckpoint | None:
        stmt = select(OrmPlaybackCheckpoint).where(
            OrmPlaybackCheckpoint.user_id == user_id,
            OrmPlaybackCheckpoint.catalog_item_id == catalog_item_id,
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return PlaybackCheckpoint(
            user_id=orm.user_id,
            catalog_item_id=orm.catalog_item_id,
            content_version_id=orm.content_version_id,
            position_ms=orm.position_ms,
            updated_at=orm.updated_at,
        )

    async def save_checkpoint(self, checkpoint: PlaybackCheckpoint) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO playback_checkpoints (user_id, catalog_item_id, content_version_id, position_ms, updated_at)
                VALUES (:user_id, :catalog_item_id, :content_version_id, :position_ms, :updated_at)
                ON CONFLICT (user_id, catalog_item_id) DO UPDATE SET
                    content_version_id = EXCLUDED.content_version_id,
                    position_ms = EXCLUDED.position_ms,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "user_id": checkpoint.user_id,
                "catalog_item_id": checkpoint.catalog_item_id,
                "content_version_id": checkpoint.content_version_id,
                "position_ms": checkpoint.position_ms,
                "updated_at": _strip_tz(checkpoint.updated_at),
            },
        )

    async def list_resume(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PlaybackCheckpoint], int]:
        count_stmt = (
            select(func.count(OrmPlaybackCheckpoint.catalog_item_id))
            .where(OrmPlaybackCheckpoint.user_id == user_id)
        )
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = (
            select(OrmPlaybackCheckpoint)
            .where(OrmPlaybackCheckpoint.user_id == user_id)
            .order_by(desc(OrmPlaybackCheckpoint.updated_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        checkpoints = [
            PlaybackCheckpoint(
                user_id=r.user_id,
                catalog_item_id=r.catalog_item_id,
                content_version_id=r.content_version_id,
                position_ms=r.position_ms,
                updated_at=r.updated_at,
            )
            for r in result.scalars().all()
        ]
        return checkpoints, total

    async def get_start_receipt(self, user_id, key):
        result = await self._session.execute(text("SELECT request_hash, response FROM playback_start_receipts WHERE user_id=:uid AND idempotency_key=:key"), {"uid":user_id, "key":key})
        row = result.mappings().first()
        return dict(row) if row else None

    async def save_start_receipt(self, user_id, key, request_hash, response):
        await self._session.execute(text("""INSERT INTO playback_start_receipts(user_id,idempotency_key,request_hash,playback_id,response)
            VALUES (:uid,:key,:hash,:pid,CAST(:response AS jsonb))"""),
            {"uid":user_id,"key":key,"hash":request_hash,"pid":response["session"]["id"],"response":json.dumps(response, default=str)})

    async def get_learning_preferences(self, user_id: str) -> LearningPreferences:
        stmt = select(OrmLearningPreferences).where(OrmLearningPreferences.user_id == user_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if not orm:
            return LearningPreferences(
                user_id=user_id,
                daily_goal_minutes=15,
                timezone="Asia/Ho_Chi_Minh",
                revision=1,
                effective_at=now,
                created_at=now,
                updated_at=now,
                preferred_topic_ids=[],
            )
        return LearningPreferences(
            user_id=orm.user_id,
            daily_goal_minutes=orm.daily_goal_minutes,
            timezone=orm.timezone,
            revision=orm.revision,
            effective_at=orm.effective_at,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            preferred_topic_ids=list(orm.preferred_topic_ids or []),
        )

    async def get_effective_learning_preferences(self, user_id: str, at: datetime) -> LearningPreferences:
        result = await self._session.execute(text("""
            SELECT * FROM learning_preference_versions
            WHERE user_id=:uid AND effective_at<=:at
            ORDER BY effective_at DESC, revision DESC LIMIT 1
        """), {"uid": user_id, "at": _strip_tz(at)})
        row = result.mappings().first()
        if row is None:
            return LearningPreferences(user_id=user_id, daily_goal_minutes=15,
                timezone="Asia/Ho_Chi_Minh", revision=1, effective_at=at,
                created_at=at, updated_at=at)
        return LearningPreferences(user_id=user_id, daily_goal_minutes=row["daily_goal_minutes"],
            timezone=row["timezone"], revision=row["revision"], effective_at=row["effective_at"],
            created_at=row["effective_at"], updated_at=row["effective_at"])

    async def save_preference_version(self, pref: LearningPreferences) -> None:
        await self._session.execute(text("""
            INSERT INTO learning_preference_versions(user_id, revision, effective_at, daily_goal_minutes, timezone)
            VALUES (:uid, :rev, :at, :goal, :tz)
            ON CONFLICT(user_id, effective_at) DO UPDATE SET
                revision=EXCLUDED.revision, daily_goal_minutes=EXCLUDED.daily_goal_minutes,
                timezone=EXCLUDED.timezone
        """), {"uid":pref.user_id, "rev":pref.revision, "at":_strip_tz(pref.effective_at),
               "goal":pref.daily_goal_minutes, "tz":pref.timezone})

    async def save_learning_preferences(self, pref: LearningPreferences) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO learning_preferences (user_id, daily_goal_minutes, timezone, revision, effective_at, preferred_topic_ids, created_at, updated_at)
                VALUES (:user_id, :daily_goal_minutes, :timezone, :revision, :effective_at, :preferred_topic_ids, :created_at, :updated_at)
                ON CONFLICT (user_id) DO UPDATE SET
                    daily_goal_minutes = EXCLUDED.daily_goal_minutes,
                    timezone = EXCLUDED.timezone,
                    revision = EXCLUDED.revision,
                    effective_at = EXCLUDED.effective_at,
                    preferred_topic_ids = EXCLUDED.preferred_topic_ids,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "user_id": pref.user_id,
                "daily_goal_minutes": pref.daily_goal_minutes,
                "timezone": pref.timezone,
                "revision": pref.revision,
                "effective_at": _strip_tz(pref.effective_at),
                "preferred_topic_ids": json.dumps(pref.preferred_topic_ids),
                "created_at": _strip_tz(pref.created_at),
                "updated_at": _strip_tz(pref.updated_at),
            },
        )

    async def record_daily_active_ms(
        self,
        user_id: str,
        date_str: str,
        timezone_str: str,
        delta_ms: int,
        goal_minutes: int,
        policy_revision: int = 1,
    ) -> LearnerDailyActivity:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        goal_ms = goal_minutes * 60 * 1000
        result = await self._session.execute(
            text(
                """
                INSERT INTO learner_daily_activity (user_id, date, policy_revision, timezone, active_ms, goal_minutes, goal_met, updated_at)
                VALUES (:user_id, :date, :policy_revision, :timezone, CAST(:delta_ms AS integer), CAST(:goal_minutes AS integer), (CAST(:goal_ms AS integer) > 0 AND CAST(:delta_ms AS integer) >= CAST(:goal_ms AS integer)), :updated_at)
                ON CONFLICT (user_id, date, policy_revision) DO UPDATE SET
                    active_ms = learner_daily_activity.active_ms + CAST(:delta_ms AS integer),
                    goal_met = ((learner_daily_activity.active_ms + CAST(:delta_ms AS integer)) >= learner_daily_activity.goal_minutes * 60000 AND learner_daily_activity.goal_minutes > 0),
                    updated_at = :updated_at
                RETURNING *
                """
            ),
            {
                "user_id": user_id,
                "date": date_str,
                "policy_revision": policy_revision,
                "timezone": timezone_str,
                "delta_ms": delta_ms,
                "goal_minutes": goal_minutes,
                "goal_ms": goal_ms,
                "updated_at": now,
            },
        )
        row = result.mappings().one()
        return LearnerDailyActivity(**dict(row))

    async def get_daily_activity_range(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
    ) -> list[LearnerDailyActivity]:
        stmt = (
            select(OrmLearnerDailyActivity)
            .where(
                OrmLearnerDailyActivity.user_id == user_id,
                OrmLearnerDailyActivity.date >= from_date,
                OrmLearnerDailyActivity.date <= to_date,
            )
            .order_by(OrmLearnerDailyActivity.date.asc())
        )
        res = await self._session.execute(stmt)
        return [
            LearnerDailyActivity(
                user_id=r.user_id,
                date=r.date,
                policy_revision=r.policy_revision,
                timezone=r.timezone,
                active_ms=r.active_ms,
                goal_minutes=r.goal_minutes,
                goal_met=r.goal_met,
                updated_at=r.updated_at,
            )
            for r in res.scalars().all()
        ]

    async def get_latest_history_deletion_cutoff(self, user_id: str) -> datetime | None:
        stmt = (
            select(func.max(OrmHistoryDeletion.cutoff_time))
            .where(
                OrmHistoryDeletion.user_id == user_id,
                OrmHistoryDeletion.status.in_(["queued", "running", "completed"]),
            )
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_watch_history(
        self,
        user_id: str,
        cutoff_time: datetime | None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[WatchHistoryItemProjection], str | None]:
        stmt = (
            select(
                OrmPlayback,
                OrmCatalogItem.title_internal,
                OrmCatalogItem.media_type,
                OrmCatalogItem.topic_id,
                OrmCatalogItem.duration_seconds,
            )
            .outerjoin(OrmCatalogItem, OrmPlayback.catalog_item_id == OrmCatalogItem.id)
            .where(OrmPlayback.user_id == user_id)
        )
        if cutoff_time is not None:
            cutoff_unaware = cutoff_time.replace(tzinfo=None) if cutoff_time.tzinfo else cutoff_time
            stmt = stmt.where(OrmPlayback.created_at > cutoff_unaware)

        if cursor:
            try:
                # cursor format: <created_at_timestamp>_<playback_id>
                parts = cursor.split("_", 1)
                cursor_ts = datetime.fromisoformat(parts[0])
                cursor_id = parts[1]
                stmt = stmt.where(
                    (OrmPlayback.created_at < cursor_ts)
                    | ((OrmPlayback.created_at == cursor_ts) & (OrmPlayback.id < cursor_id))
                )
            except Exception:
                pass

        stmt = stmt.order_by(desc(OrmPlayback.created_at), desc(OrmPlayback.id)).limit(limit + 1)
        res = await self._session.execute(stmt)
        rows = res.all()

        items: list[WatchHistoryItemProjection] = []
        has_next = len(rows) > limit
        selected_rows = rows[:limit]

        for p, title_internal, media_type, topic_id, duration_seconds in selected_rows:
            items.append(
                WatchHistoryItemProjection(
                    playback_id=p.id,
                    catalog_item_id=p.catalog_item_id,
                    title_jp=title_internal,
                    item_type=media_type or "video",
                    topic_id=topic_id or "general",
                    duration_seconds=duration_seconds or 0,
                    status=p.status,
                    last_position_ms=p.last_position_ms,
                    total_active_ms=p.total_active_ms,
                    content_version_id=p.content_version_id,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )

        next_cursor = None
        if has_next and selected_rows:
            last_p = selected_rows[-1][0]
            next_cursor = f"{last_p.created_at.isoformat()}_{last_p.id}"

        return items, next_cursor

    async def create_history_deletion_job(self, job: HistoryDeletionJob) -> HistoryDeletionJob:
        orm = OrmHistoryDeletion(
            id=job.id,
            user_id=job.user_id,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            cutoff_time=job.cutoff_time.replace(tzinfo=None) if job.cutoff_time.tzinfo else job.cutoff_time,
            records_deleted=job.records_deleted,
            attempts=job.attempts,
            error_message=job.error_message,
            created_at=job.created_at.replace(tzinfo=None) if job.created_at.tzinfo else job.created_at,
            updated_at=job.updated_at.replace(tzinfo=None) if job.updated_at.tzinfo else job.updated_at,
            completed_at=job.completed_at.replace(tzinfo=None) if (job.completed_at and job.completed_at.tzinfo) else job.completed_at,
        )
        self._session.add(orm)
        await self._session.flush()
        return job

    async def get_history_deletion_job(self, job_id: str) -> HistoryDeletionJob | None:
        stmt = select(OrmHistoryDeletion).where(OrmHistoryDeletion.id == job_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return HistoryDeletionJob(
            id=orm.id,
            user_id=orm.user_id,
            status=DeletionStatus(orm.status),
            cutoff_time=orm.cutoff_time,
            records_deleted=orm.records_deleted,
            attempts=orm.attempts,
            error_message=orm.error_message,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            completed_at=orm.completed_at,
        )

    async def claim_next_history_deletion_job(self) -> HistoryDeletionJob | None:
        stmt = (
            select(OrmHistoryDeletion)
            .where(
                OrmHistoryDeletion.status.in_(["queued", "failed"]),
                OrmHistoryDeletion.attempts < 3,
            )
            .order_by(OrmHistoryDeletion.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        orm.status = "running"
        orm.attempts += 1
        orm.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._session.flush()
        return HistoryDeletionJob(
            id=orm.id,
            user_id=orm.user_id,
            status=DeletionStatus.RUNNING,
            cutoff_time=orm.cutoff_time,
            records_deleted=orm.records_deleted,
            attempts=orm.attempts,
            error_message=orm.error_message,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            completed_at=orm.completed_at,
        )

    async def update_history_deletion_job(self, job: HistoryDeletionJob) -> None:
        stmt = select(OrmHistoryDeletion).where(OrmHistoryDeletion.id == job.id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if orm:
            orm.status = job.status.value if hasattr(job.status, "value") else str(job.status)
            orm.records_deleted = job.records_deleted
            orm.attempts = job.attempts
            orm.error_message = job.error_message
            orm.updated_at = job.updated_at.replace(tzinfo=None) if job.updated_at.tzinfo else job.updated_at
            orm.completed_at = job.completed_at.replace(tzinfo=None) if (job.completed_at and job.completed_at.tzinfo) else job.completed_at
            await self._session.flush()

    async def purge_watch_history_before_cutoff(self, user_id: str, cutoff_time: datetime) -> int:
        cutoff_unaware = cutoff_time.replace(tzinfo=None) if cutoff_time.tzinfo else cutoff_time
        # Count playbacks to be deleted
        count_stmt = select(func.count(OrmPlayback.id)).where(
            OrmPlayback.user_id == user_id,
            OrmPlayback.created_at <= cutoff_unaware,
        )
        res = await self._session.execute(count_stmt)
        count = res.scalar() or 0

        # Delete playbacks (receipts cascade delete)
        del_playbacks = text(
            """
            DELETE FROM playbacks
            WHERE user_id = :user_id AND created_at <= :cutoff_time
            """
        )
        await self._session.execute(del_playbacks, {"user_id": user_id, "cutoff_time": cutoff_unaware})

        # Delete checkpoints for user
        del_checkpoints = text(
            """
            DELETE FROM playback_checkpoints
            WHERE user_id = :user_id AND updated_at <= :cutoff_time
            """
        )
        await self._session.execute(del_checkpoints, {"user_id": user_id, "cutoff_time": cutoff_unaware})
        await self._session.flush()
        return count
