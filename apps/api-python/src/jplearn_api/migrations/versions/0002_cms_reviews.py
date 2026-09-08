"""FR-CAT-005 / FR-CMS-002: recorded QA rounds. No fabricated approvals."""
from alembic import op

revision = "0002_cms_reviews"
down_revision = "0001_prisma_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE catalog_items ADD COLUMN qa_round INTEGER NOT NULL DEFAULT 0")
    op.execute("""
        CREATE TABLE catalog_reviews (
            id TEXT PRIMARY KEY,
            catalog_item_id TEXT NOT NULL REFERENCES catalog_items(id),
            qa_round INTEGER NOT NULL,
            decision TEXT NOT NULL,
            notes TEXT NOT NULL,
            reviewed_by TEXT NOT NULL REFERENCES users(id),
            reviewed_at TIMESTAMP(3) WITHOUT TIME ZONE NOT NULL,
            CONSTRAINT catalog_reviews_item_round_key UNIQUE (catalog_item_id, qa_round),
            CONSTRAINT catalog_reviews_decision_check CHECK (decision IN ('approve', 'reject')),
            CONSTRAINT catalog_reviews_reject_notes_check CHECK (decision <> 'reject' OR length(btrim(notes)) > 0)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE catalog_reviews")
    op.execute("ALTER TABLE catalog_items DROP COLUMN qa_round")
