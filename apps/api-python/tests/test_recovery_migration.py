"""Upgrade rehearsal from an existing 0012 database, preserving references."""
import asyncio
import os
import asyncpg
from pg_harness import start_docker_postgres, stop_docker_postgres
from jplearn_api.entrypoints.cli.migrate import upgrade


def test_upgrade_0012_preserves_representative_learning_and_ai_state():
    project=f'jplearn-pytest-{os.getpid()}-recovery-upgrade'
    url=start_docker_postgres(project,migrate=False)
    async def seed_and_verify(before):
        conn=await asyncpg.connect(url)
        try:
            if before:
                await conn.execute("INSERT INTO users(id,email,password_hash) VALUES ('upgrade-user','upgrade@example.test','not-a-login')")
                await conn.execute("INSERT INTO topics(id,label_internal) VALUES ('upgrade-topic','Upgrade')")
                await conn.execute("""INSERT INTO catalog_items(id,topic_id,ci_level,duration_seconds,media_type,visual_support,title_internal,created_by,status)
                    VALUES ('upgrade-item','upgrade-topic',1,30,'video','high','upgrade','upgrade-user','published')""")
                await conn.execute("""INSERT INTO content_versions(id,catalog_item_id,version_number,is_published,is_frozen)
                    VALUES ('upgrade-version','upgrade-item',1,true,true)""")
                await conn.execute("""INSERT INTO scenes(
                    id,content_version_id,scene_index,start_time_seconds,end_time_seconds,title_jp,transcript_jp)
                    VALUES ('upgrade-scene','upgrade-version',0,0,10,'scene','legacy scene')""")
                await conn.execute("""INSERT INTO saved_scenes(id,user_id,scene_id)
                    VALUES ('upgrade-bookmark','upgrade-user','upgrade-scene')""")
                await conn.execute("""INSERT INTO learning_preferences(user_id,daily_goal_minutes,timezone,revision,effective_at)
                    VALUES ('upgrade-user',30,'Asia/Tokyo',4,now())""")
                await conn.execute("""INSERT INTO playbacks(
                    id,user_id,catalog_item_id,content_version_id,epoch,device_class,
                    client_instance_id,status,last_seq,total_active_ms,last_position_ms,
                    last_client_cumulative_ms)
                    VALUES ('upgrade-playback','upgrade-user','upgrade-item','upgrade-version',2,
                    'web','upgrade-browser','active',7,5000,5000,5000)""")
                await conn.execute("""INSERT INTO learner_playback_state(
                    user_id,active_playback_id,current_epoch,lease_expires_at,device_class,client_instance_id)
                    VALUES ('upgrade-user','upgrade-playback',2,now() + interval '10 minutes',
                    'web','upgrade-browser')""")
                await conn.execute("""INSERT INTO playback_checkpoints(user_id,catalog_item_id,content_version_id,position_ms)
                    VALUES ('upgrade-user','upgrade-item','upgrade-version',5000)""")
                await conn.execute("""INSERT INTO learner_daily_activity(user_id,date,timezone,active_ms,goal_minutes,goal_met)
                    VALUES ('upgrade-user','2026-09-07','Asia/Tokyo',1800000,30,true)""")
                await conn.execute("""INSERT INTO content_jobs(
                    id,catalog_item_id,content_version_id,task,status,source_hash,config_hash,
                    idempotency_key,created_by,attempt,attempt_token,lease_expires_at)
                    VALUES ('upgrade-job','upgrade-item','upgrade-version','transcript','running',
                    'source','config','upgrade-job-key','upgrade-user',1,'legacy-provider-token',now())""")
                await conn.execute("""INSERT INTO ai_quota_accounts(
                    id,user_id,name,reserved_audio_seconds,reserved_input_tokens,
                    reserved_output_tokens,reserved_cost_micros)
                    VALUES ('upgrade-quota','upgrade-user','upgrade quota',30,100,50,2500)""")
                await conn.execute("""INSERT INTO ai_usage_ledger(
                    id,account_id,job_id,user_id,idempotency_key,kind,status,provider,
                    audio_seconds,input_tokens,output_tokens,cost_micros)
                    VALUES ('upgrade-reservation','upgrade-quota','upgrade-job','upgrade-user',
                    'upgrade-reservation-key','reservation','reserved','legacy-provider',30,100,50,2500)""")
            else:
                assert await conn.fetchval("SELECT position_ms FROM playback_checkpoints WHERE user_id='upgrade-user'")==5000
                bookmark=await conn.fetchrow("SELECT * FROM saved_scenes WHERE id='upgrade-bookmark'")
                assert bookmark['user_id']=='upgrade-user' and bookmark['scene_id']=='upgrade-scene'
                playback=await conn.fetchrow("SELECT * FROM playbacks WHERE id='upgrade-playback'")
                assert playback['status']=='active' and playback['last_seq']==7 and playback['total_active_ms']==5000
                state=await conn.fetchrow("SELECT * FROM learner_playback_state WHERE user_id='upgrade-user'")
                assert state['active_playback_id']=='upgrade-playback' and state['current_epoch']==2
                row=await conn.fetchrow("SELECT * FROM learning_preference_versions WHERE user_id='upgrade-user'")
                assert row['daily_goal_minutes']==30 and row['revision']==4
                version=await conn.fetchrow("SELECT * FROM content_versions WHERE id='upgrade-version'")
                assert version['media_asset_id'] is None
                assert version['duration_source']=='legacy_metadata'
                assert version['source_sha256'] is None and version['hls_bundle_sha256'] is None
                assert await conn.fetchval("SELECT count(*) FROM content_versions WHERE catalog_item_id='upgrade-item'")==1
                activity=await conn.fetchrow("SELECT * FROM learner_daily_activity WHERE user_id='upgrade-user'")
                assert activity['active_ms']==1800000 and activity['policy_revision']==1 and activity['goal_met']
                quota=await conn.fetchrow("SELECT * FROM ai_quota_accounts WHERE id='upgrade-quota'")
                assert quota['reserved_audio_seconds']==30 and quota['reserved_cost_micros']==2500
                reservation=await conn.fetchrow("SELECT * FROM ai_usage_ledger WHERE id='upgrade-reservation'")
                assert reservation['status']=='reserved' and reservation['cost_micros']==2500
                attempt=await conn.fetchrow("SELECT * FROM ai_job_attempts WHERE job_id='upgrade-job'")
                assert attempt['id']=='legacy-provider-token' and attempt['state']=='outcome_unknown'
                assert await conn.fetchval("SELECT status FROM content_jobs WHERE id='upgrade-job'")=='failed'
        finally:
            await conn.close()
    try:
        upgrade(url,'0012_content_jobs')
        asyncio.run(seed_and_verify(True))
        upgrade(url)
        asyncio.run(seed_and_verify(False))
        upgrade(url)
        asyncio.run(seed_and_verify(False))
    finally:
        stop_docker_postgres(project)
