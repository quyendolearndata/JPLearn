"""Pin content source and duration metadata; retain explicit legacy provenance."""

from alembic import op

revision = "0014_content_source_snapshot"
down_revision = "0013_playback_recovery"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE content_versions
        ADD COLUMN media_asset_id TEXT,
        ADD COLUMN media_storage_key TEXT,
        ADD COLUMN media_hls_url TEXT,
        ADD COLUMN duration_seconds INTEGER,
        ADD COLUMN duration_source TEXT NOT NULL DEFAULT 'legacy_metadata'""")
    # Empty scene sets preserve existing published/QA items without inventing segments.
    op.execute("""INSERT INTO content_versions
        (id, catalog_item_id, version_number, is_frozen, is_published, published_at)
        SELECT md5('content-backfill:' || c.id)::uuid::text, c.id, 1, true,
               c.status = 'published', CASE WHEN c.status = 'published' THEN CURRENT_TIMESTAMP END
        FROM catalog_items c WHERE c.status IN ('published', 'level_qa')
        AND NOT EXISTS (SELECT 1 FROM content_versions v WHERE v.catalog_item_id = c.id)
        ON CONFLICT DO NOTHING""")
    op.execute("""UPDATE content_versions v SET
        media_asset_id = a.id, media_storage_key = a.storage_key,
        media_hls_url = a.hls_url, duration_seconds = c.duration_seconds
        FROM catalog_items c, media_assets a
        WHERE v.catalog_item_id = c.id AND a.catalog_item_id = c.id
        AND a.id = (SELECT min(m.id) FROM media_assets m WHERE m.catalog_item_id = c.id)""")


def downgrade():
    op.execute("""ALTER TABLE content_versions
        DROP COLUMN duration_source, DROP COLUMN duration_seconds,
        DROP COLUMN media_hls_url, DROP COLUMN media_storage_key, DROP COLUMN media_asset_id""")
