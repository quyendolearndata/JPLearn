"""AI quota accounts and usage ledger (ADR-007 PR8c).

Revision ID: 0011_ai_quota_and_usage_ledger
Revises: 0010_transcripts_analysis
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0011_ai_quota_and_usage_ledger"
down_revision = "0010_transcripts_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ai_quota_accounts: operational AI quota accounts with row-level locks
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "ai_quota_accounts" (
            "id" TEXT NOT NULL,
            "user_id" TEXT,
            "name" TEXT NOT NULL,
            "max_audio_seconds" INTEGER NOT NULL DEFAULT 3600,
            "max_input_tokens" INTEGER NOT NULL DEFAULT 1000000,
            "max_output_tokens" INTEGER NOT NULL DEFAULT 500000,
            "max_cost_micros" BIGINT NOT NULL DEFAULT 10000000,
            "reserved_audio_seconds" INTEGER NOT NULL DEFAULT 0,
            "reserved_input_tokens" INTEGER NOT NULL DEFAULT 0,
            "reserved_output_tokens" INTEGER NOT NULL DEFAULT 0,
            "reserved_cost_micros" BIGINT NOT NULL DEFAULT 0,
            "used_audio_seconds" INTEGER NOT NULL DEFAULT 0,
            "used_input_tokens" INTEGER NOT NULL DEFAULT 0,
            "used_output_tokens" INTEGER NOT NULL DEFAULT 0,
            "used_cost_micros" BIGINT NOT NULL DEFAULT 0,
            "policy_version" TEXT NOT NULL DEFAULT 'v1',
            "is_active" BOOLEAN NOT NULL DEFAULT true,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "ai_quota_accounts_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "ai_quota_accounts_user_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "ai_quota_accounts_reserved_bounds" CHECK (
                "reserved_audio_seconds" >= 0 AND
                "reserved_input_tokens" >= 0 AND
                "reserved_output_tokens" >= 0 AND
                "reserved_cost_micros" >= 0
            ),
            CONSTRAINT "ai_quota_accounts_used_bounds" CHECK (
                "used_audio_seconds" >= 0 AND
                "used_input_tokens" >= 0 AND
                "used_output_tokens" >= 0 AND
                "used_cost_micros" >= 0
            )
        );
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ai_quota_accounts_user_idx" ON "ai_quota_accounts"("user_id");'
    )

    # 2. ai_usage_ledger: immutable usage events (reservation, settlement, release, reconciliation)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "ai_usage_ledger" (
            "id" TEXT NOT NULL,
            "account_id" TEXT NOT NULL,
            "job_id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "idempotency_key" TEXT NOT NULL,
            "kind" TEXT NOT NULL,
            "status" TEXT NOT NULL DEFAULT 'reserved',
            "provider" TEXT NOT NULL,
            "provider_request_id" TEXT,
            "attempt" INTEGER NOT NULL DEFAULT 1,
            "audio_seconds" INTEGER NOT NULL DEFAULT 0,
            "input_tokens" INTEGER NOT NULL DEFAULT 0,
            "output_tokens" INTEGER NOT NULL DEFAULT 0,
            "cost_micros" BIGINT NOT NULL DEFAULT 0,
            "currency" TEXT NOT NULL DEFAULT 'USD',
            "policy_version" TEXT NOT NULL DEFAULT 'v1',
            "description" TEXT,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "settled_at" TIMESTAMP(3),
            CONSTRAINT "ai_usage_ledger_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "ai_usage_ledger_account_fkey" FOREIGN KEY ("account_id") REFERENCES "ai_quota_accounts"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "ai_usage_ledger_user_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
            CONSTRAINT "ai_usage_ledger_account_idem_kind_key" UNIQUE ("account_id", "idempotency_key", "kind")
        );
        """
    )
    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS "ai_usage_ledger_provider_req_att_kind_key" ON "ai_usage_ledger"("provider", "provider_request_id", "attempt", "kind") WHERE "provider_request_id" IS NOT NULL;'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ai_usage_ledger_user_created_idx" ON "ai_usage_ledger"("user_id", "created_at");'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ai_usage_ledger_account_created_idx" ON "ai_usage_ledger"("account_id", "created_at");'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ai_usage_ledger_job_status_idx" ON "ai_usage_ledger"("job_id", "status");'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "ai_usage_ledger" CASCADE;')
    op.execute('DROP TABLE IF EXISTS "ai_quota_accounts" CASCADE;')
