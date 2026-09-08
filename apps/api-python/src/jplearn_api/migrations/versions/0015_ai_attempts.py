"""Durable provider attempts and manual reconciliation (R6)."""

from alembic import op

revision = "0015_ai_attempts"
down_revision = "0014_content_source_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ai_job_attempts (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES content_jobs(id) ON DELETE RESTRICT,
            attempt_number INTEGER NOT NULL,
            provider TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL,
            lease_expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            provider_request_id TEXT,
            usage JSONB,
            evidence TEXT,
            resolved_by TEXT REFERENCES users(id) ON DELETE RESTRICT,
            resolution_hash TEXT,
            CONSTRAINT ai_attempt_job_number_key UNIQUE(job_id, attempt_number),
            CONSTRAINT ai_attempt_number_check CHECK(attempt_number > 0),
            CONSTRAINT ai_attempt_state_check CHECK(state IN ('running','outcome_unknown','settled','not_billed'))
        )
    """)
    op.execute("CREATE INDEX ai_attempt_state_lease_idx ON ai_job_attempts(state, lease_expires_at)")
    # A legacy running call has an uncertain outcome. Preserve it for review,
    # never auto-resubmit it after migration.
    op.execute("""
        INSERT INTO ai_job_attempts(id, job_id, attempt_number, provider, idempotency_key,
            state, lease_expires_at, created_at, updated_at, evidence)
        SELECT COALESCE(attempt_token, 'legacy-attempt-' || id), id, GREATEST(attempt, 1),
            COALESCE(provenance->>'provider', 'unknown'), 'legacy-' || id,
            'outcome_unknown', COALESCE(lease_expires_at, CURRENT_TIMESTAMP),
            created_at, CURRENT_TIMESTAMP, 'Legacy in-flight job; operator reconciliation required'
        FROM content_jobs WHERE status = 'running'
    """)
    op.execute("""UPDATE content_jobs SET status='failed', attempt_token=NULL,
        lease_expires_at=NULL, error_message='Legacy provider outcome unknown; reconcile attempt',
        updated_at=CURRENT_TIMESTAMP WHERE status='running'""")


def downgrade() -> None:
    # The migration CLI separately blocks destructive downgrades outside an
    # explicitly authorized environment. Keep the Alembic revision reversible
    # so isolated upgrade/downgrade verification remains possible.
    op.execute("DROP TABLE ai_job_attempts")
