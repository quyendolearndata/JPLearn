"""Durable preference policies and idempotent playback starts."""
from alembic import op
revision = "0013_playback_recovery"
down_revision = "0012_content_jobs"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""CREATE TABLE learning_preference_versions (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        revision INTEGER NOT NULL,
        effective_at TIMESTAMP(3) NOT NULL,
        daily_goal_minutes INTEGER NOT NULL CHECK (daily_goal_minutes BETWEEN 0 AND 120),
        timezone TEXT NOT NULL,
        PRIMARY KEY(user_id, effective_at)
    )""")
    # Historical effective times were not reliable. Adopt known policy from migration time only.
    op.execute("""INSERT INTO learning_preference_versions
        SELECT user_id, revision, CURRENT_TIMESTAMP, daily_goal_minutes, timezone FROM learning_preferences""")
    op.execute("""CREATE TABLE playback_start_receipts (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        playback_id TEXT NOT NULL,
        response JSONB NOT NULL,
        created_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, idempotency_key)
    )""")

def downgrade():
    op.execute("DROP TABLE playback_start_receipts")
    op.execute("DROP TABLE learning_preference_versions")
