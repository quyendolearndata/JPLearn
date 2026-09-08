"""Application handlers for Playback sessions, Heartbeat accounting, and Resume checkpoints.

Enforces:
- Single active playback lease per user (UC-L17)
- Cumulative heartbeat verification with server clock & playback rate (FR-WAT-001)
- Strict sequence matching and idempotency receipts
- Midnight split and timezone-aware daily activity aggregation
- FR-NEG boundaries: metric name is active_watch_seconds / active_ms, zero grammar/CI assumptions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from jplearn_api.application.commands import (
    EndPlaybackCommand,
    SendCheckpointCommand,
    StartPlaybackCommand,
)
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import (
    GetItemResumeQuery,
    GetPlaybackQuery,
    ListResumeQuery,
)
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
)
from jplearn_api.domain.playback import (
    CLOCK_SKEW_TOLERANCE_MS,
    DEFAULT_TIMEZONE,
    HEARTBEAT_GAP_THRESHOLD_SECONDS,
    LEASE_DURATION_SECONDS,
    PlaybackCheckpoint,
    PlaybackReceipt,
    PlaybackSession,
    PlaybackStatus,
)


def split_delta_by_timezone(
    start_time: datetime,
    end_time: datetime,
    delta_ms: int,
    tz_name: str = DEFAULT_TIMEZONE,
) -> list[tuple[str, int]]:
    """Split delta_ms across calendar days in tz_name timezone.

    Preserves exact sum: sum(allocated_ms) == delta_ms.
    """
    if delta_ms <= 0:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo(DEFAULT_TIMEZONE)
        return [(end_time.astimezone(tz).strftime("%Y-%m-%d"), 0)]

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)

    start_local = start_time.astimezone(tz)
    end_local = end_time.astimezone(tz)

    start_date = start_local.strftime("%Y-%m-%d")
    end_date = end_local.strftime("%Y-%m-%d")

    if start_date == end_date:
        return [(start_date, delta_ms)]

    # Split at local midnight
    next_day = start_local.date() + timedelta(days=1)
    midnight_local = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=tz)

    total_duration_ms = max(1, int((end_time - start_time).total_seconds() * 1000))
    ms_before_midnight = max(
        0, int((midnight_local.astimezone(UTC) - start_time.astimezone(UTC)).total_seconds() * 1000)
    )

    ratio = min(1.0, max(0.0, ms_before_midnight / total_duration_ms))
    allocated_day1 = int(round(delta_ms * ratio))
    allocated_day2 = delta_ms - allocated_day1

    results: list[tuple[str, int]] = []
    if allocated_day1 > 0:
        results.append((start_date, allocated_day1))
    if allocated_day2 > 0:
        results.append((end_date, allocated_day2))
    if not results:
        results.append((end_date, delta_ms))
    return results


async def handle_start_playback(
    cmd: StartPlaybackCommand,
    uow: AsyncUnitOfWork,
) -> tuple[PlaybackSession, PlaybackCheckpoint | None]:
    """Start a new playback session or take over an existing active lease."""
    async with uow:
        device_class = (cmd.device_info.get("device_class") if cmd.device_info else None) or "web"
        client_instance_id = cmd.device_id
        state = await uow.playbacks.acquire_learner_playback_lock(
            cmd.user_id,
            device_class=device_class,
            client_instance_id=client_instance_id,
        )
        fingerprint = hashlib.sha256(json.dumps(asdict(cmd), sort_keys=True, default=str).encode()).hexdigest()
        if cmd.idempotency_key:
            saved = await uow.playbacks.get_start_receipt(cmd.user_id, cmd.idempotency_key)
            if saved:
                if saved["request_hash"] != fingerprint:
                    raise ConflictError("Start key reused with a different payload")
                data = dict(saved["response"]["session"])
                data["status"] = PlaybackStatus(data["status"])
                for name in ("last_server_time", "created_at", "updated_at", "closed_at"):
                    if isinstance(data[name], str):
                        data[name] = datetime.fromisoformat(data[name])
                previous = PlaybackSession(**data)
                resume = saved["response"].get("resume")
                if resume:
                    resume = dict(resume)
                    if isinstance(resume["updated_at"], str):
                        resume["updated_at"] = datetime.fromisoformat(resume["updated_at"])
                    resume = PlaybackCheckpoint(**resume)
                cutoff = await uow.playbacks.get_latest_history_deletion_cutoff(cmd.user_id)
                if cutoff is not None and previous.created_at.replace(tzinfo=UTC) <= cutoff.replace(tzinfo=UTC):
                    previous.last_position_ms = 0
                    resume = None
                return previous, resume
        catalog_item = await uow.catalog.get_by_id(cmd.catalog_item_id)
        if catalog_item is None:
            raise EntityNotFoundError("Catalog item not found")
        if catalog_item.status != "published":
            raise InvalidDomainStateError("Cannot play an unpublished catalog item")
        published_version = await uow.content.get_published_by_catalog_item_id(cmd.catalog_item_id)
        content_version_id = published_version.id if published_version else f"{cmd.catalog_item_id}-v1"
        if cmd.content_version_id is not None and cmd.content_version_id != content_version_id:
            raise ConflictError("Published content version changed; reload before starting")

        now = datetime.now(UTC)

        # 3. Check single active lease & epoch bump (UC-L17 / P1.3)
        if state.active_playback_id is not None:
            # If there's an active lease on a different device instance and takeover wasn't requested:
            if state.is_lease_active(now) and state.client_instance_id != client_instance_id and not cmd.take_over:
                raise ConflictError("Another playback session is currently active on a different device")

            # In all cases when switching to a new active session, bump epoch and supersede previous session
            state.bump_epoch()
            old_session = await uow.playbacks.get_playback(state.active_playback_id)
            if old_session is not None and old_session.status == PlaybackStatus.ACTIVE:
                old_session.status = PlaybackStatus.SUPERSEDED
                old_session.closed_at = now
                old_session.updated_at = now
                await uow.playbacks.update_playback(old_session)

        # 4. Create new playback session
        new_playback_id = str(uuid4())
        lease_expires = now + timedelta(seconds=LEASE_DURATION_SECONDS)

        state.active_playback_id = new_playback_id
        state.client_instance_id = client_instance_id
        state.device_class = device_class
        state.lease_expires_at = lease_expires
        state.updated_at = now
        await uow.playbacks.update_learner_playback_state(state)

        # 5. Retrieve existing checkpoint for resume (UC-L16)
        resume_cp = await uow.playbacks.get_checkpoint(cmd.user_id, cmd.catalog_item_id)
        cutoff = await uow.playbacks.get_latest_history_deletion_cutoff(cmd.user_id)
        if resume_cp is not None and cutoff is not None:
            resume_time = (
                resume_cp.updated_at if resume_cp.updated_at.tzinfo else resume_cp.updated_at.replace(tzinfo=UTC)
            )
            cutoff_time = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=UTC)
            if resume_time <= cutoff_time:
                resume_cp = None
        if resume_cp is not None and resume_cp.content_version_id != content_version_id:
            resume_cp = None
        initial_position_ms = resume_cp.position_ms if resume_cp is not None else 0

        session = PlaybackSession(
            id=new_playback_id,
            user_id=cmd.user_id,
            catalog_item_id=cmd.catalog_item_id,
            content_version_id=content_version_id,
            epoch=state.current_epoch,
            device_class=device_class,
            client_instance_id=client_instance_id,
            status=PlaybackStatus.ACTIVE,
            last_seq=0,
            total_active_ms=0,
            last_position_ms=initial_position_ms,
            last_server_time=now,
            last_client_cumulative_ms=0,
            created_at=now,
            updated_at=now,
            closed_at=None,
        )

        await uow.playbacks.create_playback(session)
        if cmd.idempotency_key:
            await uow.playbacks.save_start_receipt(
                cmd.user_id,
                cmd.idempotency_key,
                fingerprint,
                {"session": asdict(session), "resume": asdict(resume_cp) if resume_cp else None},
            )
        await uow.commit()

        return session, resume_cp


async def handle_send_checkpoint(
    cmd: SendCheckpointCommand,
    uow: AsyncUnitOfWork,
    *,
    credit_enabled: bool = True,
    auto_commit: bool = True,
) -> tuple[PlaybackReceipt, PlaybackSession]:
    """Process consecutive heartbeat checkpoint with anti-cheat accounting."""
    async with uow:
        # 1. Lock the authenticated learner first. A valid started playback
        # already owns this row; invalid IDs roll back any first-use row.
        state = await uow.playbacks.acquire_learner_playback_lock(
            cmd.user_id,
            device_class="playback",
            client_instance_id=cmd.playback_id,
        )

        now = datetime.now(UTC)

        session = await uow.playbacks.get_playback(cmd.playback_id)
        if session is None or session.user_id != cmd.user_id:
            raise EntityNotFoundError("Playback session not found")

        # 3. Sequence & idempotency check with receipt.
        # P1.7: Check receipt before live state to allow idempotent retries.
        request_hash = hashlib.sha256(json.dumps(asdict(cmd), sort_keys=True, default=str).encode()).hexdigest()
        existing_receipt = await uow.playbacks.get_receipt(cmd.playback_id, cmd.seq)
        if existing_receipt is not None:
            if existing_receipt.request_hash == request_hash:
                return existing_receipt, session
            raise ConflictError(f"Duplicate sequence {cmd.seq} with conflicting payload")

        # 4. Check session status and epoch (only for new checkpoints)
        if session.status == PlaybackStatus.SUPERSEDED:
            raise ConflictError("Playback session has been superseded by another device/session")
        if session.status in (PlaybackStatus.COMPLETED, PlaybackStatus.ABANDONED):
            raise ConflictError("Playback session is already closed")

        if cmd.client_epoch != session.epoch or session.epoch != state.current_epoch:
            session.status = PlaybackStatus.SUPERSEDED
            session.closed_at = now
            session.updated_at = now
            await uow.playbacks.update_playback(session)
            raise ConflictError("Epoch mismatch or session superseded")

        if state.active_playback_id != session.id or not state.is_lease_active(now):
            raise ConflictError("Playback lease expired or belongs to another session")

        # Sequence progression check
        if cmd.seq <= session.last_seq:
            raise ConflictError(f"Sequence {cmd.seq} is older than last acknowledged {session.last_seq}")
        elif cmd.seq != session.last_seq + 1:
            raise ConflictError(f"Sequence gap: expected {session.last_seq + 1}, received {cmd.seq}")

        # 5. Monotonicity check
        client_delta_ms = cmd.client_cumulative_active_ms - session.last_client_cumulative_ms
        if client_delta_ms < 0:
            raise ConflictError("Client cumulative active time cannot decrease")

        # 6. Heartbeat accounting (P1.6: Wall-clock active time ceiling, no rate multiplication)
        accepted_delta_ms = 0
        last_server_time = session.last_server_time
        last_time_aware = last_server_time if last_server_time.tzinfo else last_server_time.replace(tzinfo=UTC)
        server_elapsed_ms = max(0, int((now - last_time_aware).total_seconds() * 1000))
        gap_threshold_ms = HEARTBEAT_GAP_THRESHOLD_SECONDS * 1000

        if server_elapsed_ms > gap_threshold_ms:
            # Heartbeat gap exceeded (> 30s) -> reset reference point with zero credit
            accepted_delta_ms = 0
        else:
            max_allowed = server_elapsed_ms + CLOCK_SKEW_TOLERANCE_MS
            started = (
                session.created_at.replace(tzinfo=UTC) if session.created_at.tzinfo is None else session.created_at
            )
            remaining_wall_ms = max(
                0, int((now - started).total_seconds() * 1000) + CLOCK_SKEW_TOLERANCE_MS - session.total_active_ms
            )
            accepted_delta_ms = max(0, min(client_delta_ms, max_allowed, remaining_wall_ms))
        if not credit_enabled:
            accepted_delta_ms = 0

        # 7. Timezone-aware daily activity aggregation
        if accepted_delta_ms > 0:
            final = await uow.playbacks.get_effective_learning_preferences(cmd.user_id, now)
            boundary = (
                final.effective_at.replace(tzinfo=UTC) if final.effective_at.tzinfo is None else final.effective_at
            )
            first = final
            if last_time_aware < boundary < now:
                first = await uow.playbacks.get_effective_learning_preferences(cmd.user_id, last_time_aware)
            spans = [(last_time_aware, now, accepted_delta_ms, first)]
            if last_time_aware < boundary < now and (first.timezone, first.daily_goal_minutes) != (
                final.timezone,
                final.daily_goal_minutes,
            ):
                before = int(
                    accepted_delta_ms
                    * (boundary - last_time_aware).total_seconds()
                    / (now - last_time_aware).total_seconds()
                )
                spans = [(last_time_aware, boundary, before, first), (boundary, now, accepted_delta_ms - before, final)]
            for start, end, amount, pref in spans:
                for date_str, alloc_ms in split_delta_by_timezone(start, end, amount, pref.timezone):
                    if alloc_ms > 0:
                        await uow.playbacks.record_daily_active_ms(
                            user_id=cmd.user_id,
                            date_str=date_str,
                            timezone_str=pref.timezone,
                            delta_ms=alloc_ms,
                            goal_minutes=pref.daily_goal_minutes,
                            policy_revision=pref.revision,
                        )

        # 8. Update Checkpoint for Resume
        resume_cp = PlaybackCheckpoint(
            user_id=cmd.user_id,
            catalog_item_id=session.catalog_item_id,
            content_version_id=session.content_version_id,
            position_ms=cmd.position_ms,
            updated_at=now,
        )
        await uow.playbacks.save_checkpoint(resume_cp)

        # 9. Renew lease
        lease_expires = now + timedelta(seconds=LEASE_DURATION_SECONDS)
        state.lease_expires_at = lease_expires
        state.active_playback_id = session.id
        state.client_instance_id = session.client_instance_id
        state.updated_at = now
        await uow.playbacks.update_learner_playback_state(state)

        # 10. Update session state
        session.last_seq = cmd.seq
        session.last_position_ms = cmd.position_ms
        session.total_active_ms += accepted_delta_ms
        session.last_server_time = now
        session.last_client_cumulative_ms = cmd.client_cumulative_active_ms
        session.updated_at = now
        await uow.playbacks.update_playback(session)

        # 11. Create & store receipt
        response_payload = {
            "seq": cmd.seq,
            "accepted_delta_ms": accepted_delta_ms,
            "server_acknowledged_active_ms": session.total_active_ms,
            "lease_expires_at": lease_expires.isoformat(),
            "epoch": session.epoch,
        }
        receipt = PlaybackReceipt(
            playback_id=session.id,
            seq=cmd.seq,
            request_hash=request_hash,
            accepted_delta_ms=accepted_delta_ms,
            cumulative_active_ms=session.total_active_ms,
            response_payload=response_payload,
            created_at=now,
        )
        await uow.playbacks.save_receipt(receipt)
        if auto_commit:
            await uow.commit()

        return receipt, session


async def handle_end_playback(
    cmd: EndPlaybackCommand,
    uow: AsyncUnitOfWork,
    *,
    credit_enabled: bool = True,
) -> PlaybackSession:
    """Apply the final checkpoint and close under the same user lock/transaction."""
    async with uow:
        session = await uow.playbacks.get_playback(cmd.playback_id)
        if session is None or session.user_id != cmd.user_id:
            raise EntityNotFoundError("Playback session not found")
        state = await uow.playbacks.acquire_learner_playback_lock(
            cmd.user_id,
            device_class=session.device_class,
            client_instance_id=session.client_instance_id,
        )
        # Reload after lock: another writer may have committed while we waited.
        session = await uow.playbacks.get_playback(cmd.playback_id)
        if session.status != PlaybackStatus.ACTIVE:
            return session
        now = datetime.now(UTC)
        cutoff = await uow.playbacks.get_latest_history_deletion_cutoff(cmd.user_id)
        last = (
            session.last_server_time.replace(tzinfo=UTC)
            if session.last_server_time.tzinfo is None
            else session.last_server_time
        )
        if cutoff is not None:
            cutoff = cutoff.replace(tzinfo=UTC) if cutoff.tzinfo is None else cutoff
        if cutoff is not None and last <= cutoff:
            session.status = PlaybackStatus.ABANDONED
        else:
            if state.active_playback_id != session.id or state.current_epoch != session.epoch:
                raise ConflictError("Playback no longer owns the lease")
            if cmd.final_client_epoch is not None and cmd.final_client_epoch != session.epoch:
                raise ConflictError("Final checkpoint epoch mismatch")
            if cmd.final_seq is not None and cmd.final_position_ms is not None and state.is_lease_active(now):
                _, session = await handle_send_checkpoint(
                    SendCheckpointCommand(
                        user_id=cmd.user_id,
                        playback_id=cmd.playback_id,
                        seq=cmd.final_seq,
                        position_ms=cmd.final_position_ms,
                        duration_ms=cmd.final_duration_ms or 0,
                        playback_rate=cmd.final_playback_rate,
                        state="ended",
                        client_cumulative_active_ms=(
                            cmd.final_client_cumulative_active_ms
                            if cmd.final_client_cumulative_active_ms is not None
                            else session.last_client_cumulative_ms
                        ),
                        client_epoch=session.epoch,
                        scene_id=cmd.final_scene_id,
                    ),
                    uow,
                    credit_enabled=credit_enabled,
                    auto_commit=False,
                )
            session.status = PlaybackStatus.COMPLETED
        session.closed_at = now
        session.updated_at = now
        await uow.playbacks.update_playback(session)
        if state.active_playback_id == session.id:
            state.active_playback_id = None
            state.lease_expires_at = now
            state.updated_at = now
            await uow.playbacks.update_learner_playback_state(state)
        await uow.commit()
        return session


async def handle_get_playback(
    query: GetPlaybackQuery,
    uow: AsyncUnitOfWork,
) -> PlaybackSession:
    """Retrieve playback session status and reconcile lease expiry."""
    async with uow:
        session = await uow.playbacks.get_playback(query.playback_id)
        if session is None or session.user_id != query.user_id:
            raise EntityNotFoundError("Playback session not found")

        now = datetime.now(UTC)
        last_time_aware = (
            session.last_server_time
            if session.last_server_time.tzinfo
            else session.last_server_time.replace(tzinfo=UTC)
        )
        timeout_at = last_time_aware + timedelta(seconds=LEASE_DURATION_SECONDS)
        if session.status == PlaybackStatus.ACTIVE and timeout_at < now:
            session.status = PlaybackStatus.ABANDONED
            session.closed_at = timeout_at
            session.updated_at = now
            await uow.playbacks.update_playback(session)
            await uow.commit()

        return session


async def handle_list_resume(
    query: ListResumeQuery,
    uow: AsyncUnitOfWork,
) -> tuple[list[PlaybackCheckpoint], int]:
    """List resume checkpoints for the learner (UC-L16)."""
    async with uow:
        return await uow.playbacks.list_resume(query.user_id, query.offset, query.limit)


async def handle_get_item_resume(
    query: GetItemResumeQuery,
    uow: AsyncUnitOfWork,
) -> PlaybackCheckpoint:
    """Get resume checkpoint for a specific catalog item (UC-L16)."""
    async with uow:
        checkpoint = await uow.playbacks.get_checkpoint(query.user_id, query.catalog_item_id)
        if checkpoint is None:
            raise EntityNotFoundError("Resume checkpoint not found")
        return checkpoint
