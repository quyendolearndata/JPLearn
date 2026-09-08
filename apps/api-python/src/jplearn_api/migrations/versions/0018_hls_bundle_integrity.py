"""Persist HLS bundle checksums for media and content snapshots.

Revision ID: 0018_hls_bundle_integrity
Revises: 0017_activity_policy_streak
"""
from alembic import op

revision = "0018_hls_bundle_integrity"
down_revision = "0017_activity_policy_streak"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE media_assets ADD COLUMN hls_bundle_sha256 TEXT")
    op.execute("ALTER TABLE content_versions ADD COLUMN hls_bundle_sha256 TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE content_versions DROP COLUMN hls_bundle_sha256")
    op.execute("ALTER TABLE media_assets DROP COLUMN hls_bundle_sha256")
