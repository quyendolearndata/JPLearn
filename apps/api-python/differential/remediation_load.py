"""Isolated ASGI/PostgreSQL candidate benchmark. No baseline or network latency claim."""
import argparse, asyncio, json, os, time, platform
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo
import asyncpg
from httpx import AsyncClient, ASGITransport
from pg_harness import start_docker_postgres, stop_docker_postgres
from jplearn_api.entrypoints.http.app import create_app, lifespan
from jplearn_api.settings import Settings
from jplearn_api.bootstrap import create_token_service
SECRET='load-test-only-secret-with-at-least-32-bytes'


def latency_summary(values):
    ordered=sorted(values)
    return {'samples':len(ordered),'p50_ms':ordered[int(len(ordered)*.50)-1],
        'p95_ms':ordered[int(len(ordered)*.95)-1],'max_ms':max(ordered)}


async def sample_runtime(url,pool,stop,metrics):
    """Sample PostgreSQL lock waits and pool occupancy every 10 ms."""
    monitor=await asyncpg.connect(url)
    try:
        while not stop.is_set():
            row=await monitor.fetchrow("""SELECT
                count(*) FILTER (WHERE wait_event_type='Lock') AS lock_waiters,
                count(*) FILTER (WHERE state='active') AS active_connections
                FROM pg_stat_activity
                WHERE datname=current_database() AND pid<>pg_backend_pid()""")
            checked_out=int(pool.checkedout())
            metrics['sample_count']+=1
            metrics['max_checked_out']=max(metrics['max_checked_out'],checked_out)
            metrics['max_active_connections']=max(metrics['max_active_connections'],int(row['active_connections'] or 0))
            if checked_out>=pool.size(): metrics['pool_saturated_samples']+=1
            lock_waiters=int(row['lock_waiters'] or 0)
            metrics['max_lock_waiters']=max(metrics['max_lock_waiters'],lock_waiters)
            if lock_waiters:
                metrics['lock_wait_samples'].append({'at':datetime.now(timezone.utc).isoformat(),'waiters':lock_waiters})
            try: await asyncio.wait_for(stop.wait(),timeout=.01)
            except TimeoutError: pass
    finally: await monitor.close()


async def explain(conn,sql,*args):
    raw=await conn.fetchval(f'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}',*args)
    doc=json.loads(raw) if isinstance(raw,str) else raw
    statement=doc[0]
    return {'planning_time_ms':statement.get('Planning Time'),
        'execution_time_ms':statement.get('Execution Time'),'plan':statement['Plan']}


@asynccontextmanager
async def runtime_monitor(url, pool, metrics):
    stop = asyncio.Event()
    task = asyncio.create_task(sample_runtime(url, pool, stop, metrics))
    try:
        yield
    finally:
        stop.set()
        await task


async def query_plans(conn,user,clip,version,today):
    return {
        'published_content_version':await explain(conn,"""SELECT id FROM content_versions
            WHERE catalog_item_id=$1 AND is_published IS TRUE
            ORDER BY version_number DESC LIMIT 1""",clip),
        'content_scenes':await explain(conn,"SELECT id FROM scenes WHERE content_version_id=$1 ORDER BY scene_index",version),
        'daily_activity':await explain(conn,"""SELECT * FROM learner_daily_activity
            WHERE user_id=$1 AND date >= $2 AND date <= $2 ORDER BY date""",user,today),
        'scene_search_candidates':await explain(conn,"""SELECT ast.id FROM approved_scene_texts ast
            JOIN catalog_items c ON c.id=ast.catalog_item_id
            JOIN content_versions v ON v.id=ast.content_version_id
            JOIN scenes s ON s.id=ast.scene_id
            WHERE ast.is_active IS TRUE AND c.status='published' AND v.is_published IS TRUE
              AND c.ci_level<=1 AND ast.text_ja LIKE '%' || $1 || '%'
            ORDER BY ast.catalog_item_id,ast.scene_index""",'負荷検索0000-00'),
        'playback_owner':await explain(conn,"SELECT * FROM learner_playback_state WHERE user_id=$1",user),
        'watch_history':await explain(conn,"""SELECT id FROM playbacks WHERE user_id=$1
            ORDER BY created_at DESC,id DESC LIMIT 50""",user),
        'quota_account':await explain(conn,"SELECT id FROM ai_quota_accounts WHERE user_id=$1",user),
    }


async def workload(url, mode, pool_size=50):
    conn=await asyncpg.connect(url)
    users=[str(uuid4()) for _ in range(100)]
    clips=[str(uuid4()) for _ in range(1000)]
    versions=[str(uuid4()) for _ in clips]
    media=[str(uuid4()) for _ in clips]
    scene_rows=[
        (str(uuid4()),v,n,n*30,(n+1)*30,f'負荷検索{i:04d}-{n:02d}')
        for i,v in enumerate(versions) for n in range(10)
    ]
    today=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()
    try:
        await conn.executemany("INSERT INTO users(id,email,password_hash) VALUES ($1,$2,'unused')",[(u,f'{u}@load.test') for u in users])
        await conn.executemany("INSERT INTO user_roles(user_id,role) VALUES ($1,$2)",[(u,r) for u in users for r in ('learner','teacher')])
        await conn.executemany("INSERT INTO learner_progress(user_id,minutes_comprehensible,current_ci_level,updated_at) VALUES ($1,0,1,now())",[(u,) for u in users])
        await conn.execute("INSERT INTO topics(id,label_internal) VALUES ('load','load')")
        await conn.executemany("""INSERT INTO catalog_items(id,topic_id,ci_level,duration_seconds,media_type,visual_support,title_internal,created_by,status)
            VALUES ($1,'load',1,300,'video','high','load',$2,'published')""",[(c,users[0]) for c in clips])
        await conn.executemany("""INSERT INTO media_assets(id,catalog_item_id,storage_key,mime,measured_duration_ms,source_sha256)
            VALUES ($1,$2,$3,'video/mp4',300000,$4)""",[(m,c,f'load/{m}.mp4',f'{i:064x}') for i,(m,c) in enumerate(zip(media,clips),1)])
        await conn.executemany("""INSERT INTO content_versions(
            id,catalog_item_id,version_number,is_published,is_frozen,media_asset_id,media_storage_key,
            duration_seconds,measured_duration_ms,source_sha256,duration_source)
            VALUES ($1,$2,1,true,true,$3,$4,300,300000,$5,'ffprobe')""",
            [(v,c,m,f'load/{m}.mp4',f'{i:064x}') for i,(v,c,m) in enumerate(zip(versions,clips,media),1)])
        await conn.executemany("""INSERT INTO scenes(id,content_version_id,scene_index,start_time_seconds,end_time_seconds,title_jp,transcript_jp)
            VALUES ($1,$2,$3,$4,$5,'店',$6)""",scene_rows)
        transcript_rows=[(str(uuid4()),clips[i],versions[i]) for i in range(len(clips))]
        await conn.executemany("""INSERT INTO transcript_revisions(
            id,catalog_item_id,content_version_id,revision,status,segments,provenance,created_by,approved_by)
            VALUES ($1,$2,$3,1,'approved','[]'::jsonb,'manual_teacher',$4,$4)""",
            [(r,c,v,users[0]) for r,c,v in transcript_rows])
        transcript_by_version={v:r for r,_,v in transcript_rows}
        await conn.executemany("""INSERT INTO approved_scene_texts(
            id,catalog_item_id,content_version_id,scene_id,transcript_revision_id,text_ja,
            scene_index,start_time_seconds,end_time_seconds)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
            [(str(uuid4()),clips[i//10],v,s,transcript_by_version[v],text,n,start,end)
             for i,(s,v,n,start,end,text) in enumerate(scene_rows)])
        await conn.executemany("""INSERT INTO ai_quota_accounts(id,user_id,name)
            VALUES ($1,$2,'load')""",[(str(uuid4()),u) for u in users])
        await conn.execute("""INSERT INTO playbacks(id,user_id,catalog_item_id,content_version_id,device_class,client_instance_id,status)
            SELECT md5('history-'||g)::uuid::text,$1,$2,$3,'web','historical','completed' FROM generate_series(1,100000) g""",users[0],clips[0],versions[0])
        await conn.execute('ANALYZE')
        app=create_app(Settings(database_url=url,jwt_secret=SECRET,environment='test',playback_tracking_enabled=True,video_scene_breakdown_enabled=True,
            scene_search_enabled=True,staff_ai_enabled=True,
            database_pool_size=pool_size,database_max_overflow=0,database_pool_pre_ping=False))
        samples=[]
        pool_acquire_ms=[]
        runtime_metrics={'sampling_interval_ms':10,'sample_count':0,'max_checked_out':0,
            'pool_saturated_samples':0,'max_active_connections':0,'max_lock_waiters':0,
            'lock_wait_samples':[]}
        deadlocks_before=int(await conn.fetchval(
            "SELECT deadlocks FROM pg_stat_database WHERE datname=current_database()") or 0)
        correctness={}
        async with lifespan(app):
            pool=app.state.engine.sync_engine.pool
            original_do_get=pool._do_get
            def timed_do_get():
                began=time.perf_counter()
                try: return original_do_get()
                finally: pool_acquire_ms.append((time.perf_counter()-began)*1000)
            pool._do_get=timed_do_get
            async with runtime_monitor(url,pool,runtime_metrics), AsyncClient(transport=ASGITransport(app=app),base_url='http://load') as client:
                async def learner(i):
                    if mode == 'steady':
                        await asyncio.sleep(i * 15 / len(users))
                    token=create_token_service().sign_access_token(users[i],f'{users[i]}@load.test',0,SECRET)
                    headers={'Authorization':f'Bearer {token}','Idempotency-Key':str(uuid4())}
                    start=await client.post('/playbacks',headers=headers,json={'catalog_item_id':clips[i],'content_version_id':versions[i],'device_id':f'load-{i}'})
                    assert start.status_code==201,start.text
                    pid=start.json()['playback_id']; epoch=start.json()['epoch']
                    for seq in range(1,5):
                        await asyncio.sleep(15)
                        began=time.perf_counter()
                        result=await client.put(f'/playbacks/{pid}/checkpoints/{seq}',headers=headers,json={
                            'position_ms':seq*15000,'duration_ms':300000,'playback_rate':1,'state':'playing',
                            'client_cumulative_active_ms':seq*15000,'client_epoch':epoch})
                        samples.append({'operation':'checkpoint','user':i,'seq':seq,'latency_ms':(time.perf_counter()-began)*1000,'status':result.status_code})
                        assert result.status_code==200,result.text
                        assert result.json()['server_acknowledged_active_ms']==seq*15000,result.text
                        began=time.perf_counter()
                        meta=await client.get(f'/catalog/{clips[i]}/content',headers=headers)
                        samples.append({'operation':'content','user':i,'seq':seq,'latency_ms':(time.perf_counter()-began)*1000,'status':meta.status_code})
                        assert meta.status_code==200
                        began=time.perf_counter()
                        activity=await client.get(f'/me/activity?from={today}&to={today}',headers=headers)
                        samples.append({'operation':'activity','user':i,'seq':seq,'latency_ms':(time.perf_counter()-began)*1000,'status':activity.status_code})
                        assert activity.status_code==200,activity.text
                        began=time.perf_counter()
                        search=await client.get(f'/catalog/search?q=負荷検索{i:04d}-00&limit=1',headers=headers)
                        samples.append({'operation':'search','user':i,'seq':seq,'latency_ms':(time.perf_counter()-began)*1000,'status':search.status_code})
                        assert search.status_code==200 and len(search.json()['items'])==1,search.text
                    began=time.perf_counter()
                    job=await client.post(f'/staff/catalog/{clips[i]}/content-jobs',headers={
                        **headers,'Idempotency-Key':f'load-job-{i}'},json={
                        'content_version_id':versions[i],'task':'transcript','language':'ja'})
                    samples.append({'operation':'job-create','user':i,'seq':1,'latency_ms':(time.perf_counter()-began)*1000,'status':job.status_code})
                    assert job.status_code==202,job.text
                    ended=await client.post(f'/playbacks/{pid}/end',headers=headers,json={})
                    assert ended.status_code==200
                await asyncio.gather(*(learner(i) for i in range(100)))
                credit_rows=await conn.fetch("""SELECT user_id,sum(active_ms)::bigint AS active_ms
                    FROM learner_daily_activity WHERE user_id=ANY($1::text[]) GROUP BY user_id""",users)
                actual_credit={row['user_id']:int(row['active_ms']) for row in credit_rows}
                credit_mismatches={user:actual_credit.get(user,0) for user in users
                    if actual_credit.get(user,0) != 60000}
                receipt_credit=int(await conn.fetchval("""SELECT coalesce(sum(accepted_delta_ms),0)
                    FROM playback_receipts pr JOIN playbacks p ON p.id=pr.playback_id
                    WHERE p.user_id=ANY($1::text[])""",users) or 0)
                assert not credit_mismatches,credit_mismatches
                assert receipt_credit==6000000,receipt_credit
                user_token=create_token_service().sign_access_token(users[0],f'{users[0]}@load.test',0,SECRET)
                user_headers={'Authorization':f'Bearer {user_token}'}
                deletion=await client.delete('/me/watch-history',headers=user_headers)
                history_after=await client.get('/me/watch-history?limit=10',headers=user_headers)
                activity_after=await client.get(f'/me/activity?from={today}&to={today}',headers=user_headers)
                assert deletion.status_code==202,deletion.text
                assert history_after.status_code==200 and history_after.json()['items']==[],history_after.text
                assert activity_after.status_code==200,activity_after.text
                assert activity_after.json()['total_active_watch_seconds']==60,activity_after.text
                correctness={'checkpoint_credit_expected_ms':6000000,
                    'daily_activity_credit_actual_ms':sum(actual_credit.values()),
                    'receipt_credit_actual_ms':receipt_credit,
                    'credit_mismatch_count':len(credit_mismatches),
                    'all_request_errors':sum(1 for sample in samples if sample['status']>=400),
                    'history_hidden_immediately_after_delete':True,
                    'daily_activity_seconds_after_delete':activity_after.json()['total_active_watch_seconds']}
        deadlocks_after=int(await conn.fetchval(
            "SELECT deadlocks FROM pg_stat_database WHERE datname=current_database()") or 0)
        runtime_metrics['deadlocks_before']=deadlocks_before
        runtime_metrics['deadlocks_after']=deadlocks_after
        runtime_metrics['deadlocks_during_run']=deadlocks_after-deadlocks_before
        runtime_metrics['pool_saturation_ratio']=(runtime_metrics['pool_saturated_samples']/runtime_metrics['sample_count']
            if runtime_metrics['sample_count'] else 0)
        summary={}
        for op in ('checkpoint','content','activity','search','job-create'):
            values=[x['latency_ms'] for x in samples if x['operation']==op]
            summary[op]={**latency_summary(values),
                'errors':sum(1 for x in samples if x['operation']==op and x['status']>=400)}
        pool_summary=latency_summary(pool_acquire_ms)
        plans=await query_plans(conn,users[0],clips[0],versions[0],today)
        out=Path('../../docs/qa/evidence/backend-remediation');out.mkdir(parents=True,exist_ok=True)
        suffix='' if pool_size == 50 else f'-pool{pool_size}'
        (out/f'load-{mode}{suffix}-candidate.json').write_text(json.dumps({'time':datetime.now(timezone.utc).isoformat(),
            'platform':platform.platform(),'postgres':await conn.fetchval('SELECT version()'),
            'alembic_head':await conn.fetchval('SELECT version_num FROM alembic_version'),
            'scope':f'ASGI; no network latency claim; 4 rounds of 15s heartbeats; 100-client {mode}; candidate only',
            'pool':{'size':pool_size,'max_overflow':0,'pre_ping':False,
                'measurement':'QueuePool acquisition duration, instrumented in this isolated harness',
                'summary':pool_summary,'samples_ms':pool_acquire_ms},
            'dataset':{'clips':1000,'scenes':10000,'approved_scene_texts':10000,'historical_playbacks':100000,'concurrent_playbacks':100},
            'runtime':runtime_metrics,'correctness':correctness,'query_plans':plans,
            'summary':summary,'samples':samples},indent=2)+'\n')
        print(json.dumps({'summary':summary,'pool':pool_summary,'runtime':{
            key:value for key,value in runtime_metrics.items() if key != 'lock_wait_samples'},
            'correctness':correctness}))
    finally: await conn.close()
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=('burst','steady'),default='burst')
    parser.add_argument('--pool-size',type=int,choices=range(1,91),default=50)
    args=parser.parse_args()
    project=f'jplearn-pytest-{os.getpid()}-load'
    url=start_docker_postgres(project)
    try: asyncio.run(workload(url,args.mode,args.pool_size))
    finally: stop_docker_postgres(project)
