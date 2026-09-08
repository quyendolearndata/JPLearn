"""PostgreSQL/HTTP evidence for durable AI attempt operator reconciliation."""

from uuid import uuid4

import asyncpg
import pytest

from test_remediation_concurrency import (
    _create_user_with_roles,
)
from test_remediation_concurrency import (
    client_factory as client_factory,
)
from test_remediation_concurrency import (
    postgres_url as postgres_url,
)


@pytest.mark.asyncio
async def test_admin_reconciles_unknown_attempt_once_over_http(
    client_factory,
    postgres_url,
):
    client = await client_factory()
    user_id, token = await _create_user_with_roles(client, postgres_url, ["admin"])
    job_id, item_id, version_id, account_id = (str(uuid4()) for _ in range(4))
    attempt_id = str(uuid4())
    conn = await asyncpg.connect(postgres_url)
    try:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO catalog_items(
                id,topic_id,ci_level,duration_seconds,media_type,visual_support,title_internal,created_by,status)
                VALUES($1,'daily_home',1,30,'video','high','attempt-test',$2,'draft')""",
                item_id,
                user_id,
            )
            await conn.execute(
                """INSERT INTO content_versions(id,catalog_item_id,version_number)
                VALUES($1,$2,1)""",
                version_id,
                item_id,
            )
            await conn.execute(
                """INSERT INTO ai_quota_accounts(
                id,user_id,name,max_audio_seconds,max_input_tokens,max_output_tokens,max_cost_micros,
                reserved_audio_seconds,reserved_input_tokens,reserved_output_tokens,reserved_cost_micros)
                VALUES($1,$2,'attempt-test',1000,1000,1000,1000000,120,100,20,300000)""",
                account_id,
                user_id,
            )
            await conn.execute(
                """INSERT INTO content_jobs(
                id,catalog_item_id,content_version_id,task,status,source_hash,config_hash,
                idempotency_key,created_by,attempt,error_message)
                VALUES($1,$2,$3,'transcript','failed','source','config','job-key',$4,1,'outcome unknown')""",
                job_id,
                item_id,
                version_id,
                user_id,
            )
            await conn.execute(
                """INSERT INTO ai_usage_ledger(
                id,account_id,job_id,user_id,idempotency_key,kind,status,provider,attempt,
                audio_seconds,input_tokens,output_tokens,cost_micros)
                VALUES($1,$2,$3,$4,'reservation-key','reservation','outcome_unknown','test',1,120,100,20,300000)""",
                str(uuid4()),
                account_id,
                job_id,
                user_id,
            )
            await conn.execute(
                """INSERT INTO ai_job_attempts(
                id,job_id,attempt_number,provider,idempotency_key,state,lease_expires_at,created_at,updated_at,evidence)
                VALUES($1,$2,1,'test',$3,'outcome_unknown',now(),now(),now(),'transport outcome unknown')""",
                attempt_id,
                job_id,
                f"ai-attempt:{attempt_id}",
            )

        headers = {"Authorization": f"Bearer {token}"}
        listed = await client.get(f"/staff/content-jobs/{job_id}/attempts", headers=headers)
        assert listed.status_code == 200 and listed.json()[0]["state"] == "outcome_unknown"
        payload = {
            "decision": "not_billed",
            "evidence": "Provider console confirms this request was not billed.",
        }
        first = await client.post(
            f"/staff/content-jobs/{job_id}/attempts/{attempt_id}/reconcile",
            headers=headers,
            json=payload,
        )
        repeated = await client.post(
            f"/staff/content-jobs/{job_id}/attempts/{attempt_id}/reconcile",
            headers=headers,
            json=payload,
        )
        assert first.status_code == repeated.status_code == 200
        assert first.json()["state"] == "not_billed"
        conflicting = await client.post(
            f"/staff/content-jobs/{job_id}/attempts/{attempt_id}/reconcile",
            headers=headers,
            json={**payload, "evidence": "Different provider evidence for the same request."},
        )
        assert conflicting.status_code == 409
        assert (
            await conn.fetchval(
                "SELECT reserved_cost_micros FROM ai_quota_accounts WHERE id=$1",
                account_id,
            )
            == 0
        )
        assert (
            await conn.fetchval(
                """SELECT count(*) FROM ai_usage_ledger
            WHERE account_id=$1 AND kind='release'""",
                account_id,
            )
            == 1
        )
        assert (
            await conn.fetchval(
                """SELECT status FROM ai_usage_ledger
            WHERE account_id=$1 AND kind='reservation'""",
                account_id,
            )
            == "released"
        )
    finally:
        await client.aclose()
        await conn.close()
