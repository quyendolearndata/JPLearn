"""Measured duration and source integrity; legacy media explicitly remain unverified."""
from alembic import op
revision = "0016_media_probe"
down_revision = "0015_ai_attempts"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE media_assets ADD COLUMN measured_duration_ms BIGINT, ADD COLUMN source_sha256 TEXT")
    op.execute("ALTER TABLE content_versions ADD COLUMN measured_duration_ms BIGINT, ADD COLUMN source_sha256 TEXT")

def downgrade():
    op.execute("ALTER TABLE content_versions DROP COLUMN source_sha256, DROP COLUMN measured_duration_ms")
    op.execute("ALTER TABLE media_assets DROP COLUMN source_sha256, DROP COLUMN measured_duration_ms")
