import uuid

import asyncpg
import pytest

from jplearn_api.entrypoints.cli.maintenance import inventory_media_integrity


@pytest.mark.asyncio
async def test_media_integrity_inventory_lists_legacy_asset_and_pinned_version(
    live_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
):
    suffix = uuid.uuid4().hex
    user_id = f"inventory-user-{suffix}"
    topic_id = f"inventory-topic-{suffix}"
    item_id = f"inventory-item-{suffix}"
    asset_id = f"inventory-asset-{suffix}"
    version_id = f"inventory-version-{suffix}"

    conn = await asyncpg.connect(live_database_url)
    try:
        await conn.execute(
            "INSERT INTO users(id,email,password_hash) VALUES ($1,$2,'not-a-login')",
            user_id,
            f"{user_id}@example.test",
        )
        await conn.execute("INSERT INTO topics(id,label_internal) VALUES ($1,'Inventory')", topic_id)
        await conn.execute(
            """INSERT INTO catalog_items(
                id,topic_id,ci_level,duration_seconds,media_type,visual_support,
                title_internal,created_by,status)
                VALUES ($1,$2,1,30,'video','high','inventory',$3,'published')""",
            item_id,
            topic_id,
            user_id,
        )
        await conn.execute(
            """INSERT INTO media_assets(id,catalog_item_id,storage_key,hls_url,mime)
                VALUES ($1,$2,$3,$4,'video/mp4')""",
            asset_id,
            item_id,
            f"media/{asset_id}/source.mp4",
            f"media/{asset_id}/hls/master.m3u8",
        )
        await conn.execute(
            """INSERT INTO content_versions(
                id,catalog_item_id,version_number,is_frozen,is_published,
                media_asset_id,media_storage_key,media_hls_url)
                VALUES ($1,$2,1,true,true,$3,$4,$5)""",
            version_id,
            item_id,
            asset_id,
            f"media/{asset_id}/source.mp4",
            f"media/{asset_id}/hls/master.m3u8",
        )

        monkeypatch.setenv("DATABASE_URL", live_database_url)
        monkeypatch.setenv("JWT_SECRET", "test-secret-at-least-32-bytes-long-for-inventory")
        report = await inventory_media_integrity(limit=1000)

        asset = next(row for row in report["media_assets"]["candidates"] if row["id"] == asset_id)
        assert asset["missing_measured_duration"]
        assert asset["missing_source_sha256"]
        assert asset["missing_hls_bundle_sha256"]

        version = next(
            row for row in report["pinned_versions"]["candidates"] if row["id"] == version_id
        )
        assert version["legacy_duration"]
        assert version["missing_source_sha256"]
        assert version["missing_hls_bundle_sha256"]
    finally:
        await conn.execute("DELETE FROM content_versions WHERE id=$1", version_id)
        await conn.execute("DELETE FROM media_assets WHERE id=$1", asset_id)
        await conn.execute("DELETE FROM catalog_items WHERE id=$1", item_id)
        await conn.execute("DELETE FROM topics WHERE id=$1", topic_id)
        await conn.execute("DELETE FROM users WHERE id=$1", user_id)
        await conn.close()
