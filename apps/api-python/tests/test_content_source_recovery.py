"""HTTP/DB regression for QA source freezing and learner projection."""
import pytest
from test_remediation_concurrency import postgres_url, client_factory, _create_user_with_roles

@pytest.mark.asyncio
async def test_qa_pins_source_and_learner_never_gets_staff_transcript(client_factory, postgres_url):
    client=await client_factory()
    _, token=await _create_user_with_roles(client, postgres_url, ['admin','teacher','learner'])
    headers={'Authorization':f'Bearer {token}'}
    try:
        created=await client.post('/staff/catalog',headers=headers,json={'topic_id':'daily_home',
            'ci_level':1,'duration_seconds':30,'media_type':'video','visual_support':'high','title_internal':'snapshot'})
        assert created.status_code==201
        item=created.json()['id']
        media=await client.post(f'/staff/catalog/{item}/media',headers=headers,
            files={'file':('test.mp4',b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomtest','video/mp4')})
        assert media.status_code==201, media.text
        content=await client.put(f'/staff/catalog/{item}/content',headers=headers,json={'version_revision':1,
            'scenes':[{'scene_index':1,'start_time_seconds':0,'end_time_seconds':10,'title_jp':'店','transcript_jp':'staff draft'}]})
        assert content.status_code==200,content.text
        qa=await client.post(f'/staff/catalog/{item}/submit-qa',headers=headers)
        assert qa.status_code==200,qa.text
        register=await client.post(f"/staff/media/{media.json()['id']}/hls",headers=headers)
        assert register.status_code==400,register.text
        published=await client.post(f'/staff/catalog/{item}/publish',headers=headers)
        assert published.status_code==200,published.text
        learner=await client.get(f'/catalog/{item}/content',headers=headers)
        assert learner.status_code==200
        assert 'transcript_jp' not in learner.json()['scenes'][0]
        import asyncpg
        conn=await asyncpg.connect(postgres_url)
        try:
            row=await conn.fetchrow('SELECT media_asset_id,duration_seconds,duration_source,measured_duration_ms,source_sha256 FROM content_versions WHERE id=$1',content.json()['id'])
            assert row['media_asset_id']==media.json()['id']
            assert row['duration_seconds']==30
            assert row['duration_source']=='ffprobe'
            assert row['measured_duration_ms'] == media.json()['measured_duration_ms']
            assert row['source_sha256'] == media.json()['source_sha256']
        finally:
            await conn.close()
    finally:
        await client.aclose()
