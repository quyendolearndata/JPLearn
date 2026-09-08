"""Regression evidence for final accounting, start replay and future preferences."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest

from test_remediation_concurrency import postgres_url, client_factory, _create_user_with_roles
from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
from jplearn_api.bootstrap import create_uow
from jplearn_api.settings import Settings


@pytest.mark.asyncio
async def test_start_replay_final_credit_and_terminal_retry(client_factory, postgres_url):
    client = await client_factory()
    uid, token = await _create_user_with_roles(client, postgres_url, ['learner', 'admin'])
    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': str(uuid4())}
    item = await client.post('/staff/catalog', headers=headers, json={
        'topic_id':'daily_home','ci_level':1,'duration_seconds':60,
        'media_type':'video','visual_support':'high','title_internal':'recovery',
    })
    assert item.status_code == 201
    item_id = item.json()['id']
    content = await client.put(f'/staff/catalog/{item_id}/content', headers=headers,
        json={'version_revision':1,'scenes':[]})
    assert content.status_code == 200, content.text
    version_id = content.json()['id']
    conn = await asyncpg.connect(postgres_url)
    try:
        await conn.execute("UPDATE catalog_items SET status='published' WHERE id=$1", item_id)
        await conn.execute("UPDATE content_versions SET is_published=true WHERE id=$1", version_id)
        payload = {'catalog_item_id':item_id,'device_id':'web','content_version_id':version_id}
        first = await client.post('/playbacks', headers=headers, json=payload)
        assert first.status_code == 201, first.text
        retry = await client.post('/playbacks', headers=headers, json=payload)
        assert retry.json() == first.json()
        changed = await client.post('/playbacks', headers=headers, json={**payload,'device_id':'other'})
        assert changed.status_code == 409
        pid = first.json()['playback_id']
        await conn.execute("UPDATE playbacks SET created_at=now()-interval '5 seconds', last_server_time=now()-interval '5 seconds' WHERE id=$1",pid)
        final = {'final_seq':1,'final_position_ms':5000,'final_duration_ms':60000,
            'final_client_cumulative_active_ms':5000,'final_client_epoch':first.json()['epoch']}
        ended = await client.post(f'/playbacks/{pid}/end', headers=headers, json=final)
        assert ended.status_code == 200, ended.text
        assert ended.json()['server_acknowledged_active_ms'] == 5000
        again = await client.post(f'/playbacks/{pid}/end', headers=headers, json=final)
        assert again.status_code == 200
        assert again.json()['server_acknowledged_active_ms'] == 5000
        assert await conn.fetchval('SELECT active_ms FROM learner_daily_activity WHERE user_id=$1',uid) == 5000
        assert await conn.fetchval('SELECT count(*) FROM playback_receipts WHERE playback_id=$1',pid) == 1
    finally:
        await conn.close()
        await client.aclose()


@pytest.mark.asyncio
async def test_preferences_concurrent_update_and_effective_policy(client_factory, postgres_url):
    client = await client_factory()
    uid, token = await _create_user_with_roles(client, postgres_url, ['learner'])
    headers = {'Authorization':f'Bearer {token}'}
    responses = await asyncio.gather(*[
        client.put('/me/learning-preferences',headers=headers,json={
            'expected_revision':1,'daily_goal_minutes':goal,'timezone':'Pacific/Honolulu'})
        for goal in (30,120)])
    assert sorted(r.status_code for r in responses)==[200,409], [r.text for r in responses]
    pending = next(r.json() for r in responses if r.status_code==200)
    boundary = datetime.fromisoformat(pending['effective_at'].replace('Z','+00:00'))
    engine, sessions = create_engine_and_sessions(Settings(database_url=postgres_url, jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security"))
    try:
        async with sessions() as session:
            repo=create_uow(session).playbacks
            current=await repo.get_effective_learning_preferences(uid, datetime.now(timezone.utc))
            future=await repo.get_effective_learning_preferences(uid, boundary+timedelta(seconds=1))
            assert (current.daily_goal_minutes,current.timezone)==(15,'Asia/Ho_Chi_Minh')
            assert (future.daily_goal_minutes,future.timezone)==(pending['daily_goal_minutes'],'Pacific/Honolulu')
    finally:
        await engine.dispose()
        await client.aclose()
