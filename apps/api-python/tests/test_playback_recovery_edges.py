from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from jplearn_api.application.commands import EndPlaybackCommand, SendCheckpointCommand, StartPlaybackCommand
from jplearn_api.application.handlers.playback import handle_end_playback, handle_send_checkpoint, handle_start_playback
from jplearn_api.domain.errors import ConflictError
from test_playback_tracking import test_env as test_env


@pytest.mark.asyncio
async def test_expired_lease_rejects_new_checkpoint(test_env):
    u = test_env["uow"]
    s, _ = await handle_start_playback(StartPlaybackCommand("u", "item-01", "web"), u)
    async with u:
        state = await u.playbacks.acquire_learner_playback_lock("u", "web", "web")
        state.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await u.playbacks.update_learner_playback_state(state)
        await u.commit()
    with pytest.raises(ConflictError):
        await handle_send_checkpoint(SendCheckpointCommand("u", s.id, 1, 10, 60000, 1, "playing", 10, s.epoch), u)


@pytest.mark.asyncio
async def test_flag_off_and_fingerprint_and_terminal_immutability(test_env):
    u = test_env["uow"]
    s, _ = await handle_start_playback(StartPlaybackCommand("u", "item-01", "web"), u)
    cmd = SendCheckpointCommand("u", s.id, 1, 10, 60000, 1, "playing", 1000, s.epoch)
    receipt, _ = await handle_send_checkpoint(cmd, u, credit_enabled=False)
    assert receipt.accepted_delta_ms == 0
    with pytest.raises(ConflictError):
        await handle_send_checkpoint(replace(cmd, duration_ms=999), u)
    with pytest.raises(ConflictError):
        await handle_end_playback(EndPlaybackCommand("u", s.id, final_client_epoch=999), u)
    end = EndPlaybackCommand(
        "u",
        s.id,
        final_seq=2,
        final_position_ms=2000,
        final_client_cumulative_active_ms=2000,
        final_client_epoch=s.epoch,
    )
    closed = await handle_end_playback(end, u, credit_enabled=False)
    retried = await handle_end_playback(replace(end, final_seq=3, final_position_ms=50000), u)
    assert retried.last_position_ms == closed.last_position_ms == 2000
    assert retried.total_active_ms == 0
