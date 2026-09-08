"""Keep activity buckets distinct across goal/timezone policy changes."""
from alembic import op

revision = "0017_activity_policy_streak"
down_revision = "0016_media_probe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE learner_daily_activity ADD COLUMN policy_revision INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE learner_daily_activity DROP CONSTRAINT learner_daily_activity_pkey")
    op.execute("ALTER TABLE learner_daily_activity ADD CONSTRAINT learner_daily_activity_pkey PRIMARY KEY (user_id, date, policy_revision)")


def downgrade() -> None:
    # A pre-0017 schema cannot represent multiple policies on one local date.
    # The CLI guards this lossy path; retain the newest policy and total time.
    op.execute('''
        WITH totals AS (
            SELECT user_id, date, SUM(active_ms)::INTEGER AS active_ms
            FROM learner_daily_activity GROUP BY user_id, date
        ), newest AS (
            SELECT DISTINCT ON (user_id, date) user_id, date, policy_revision
            FROM learner_daily_activity ORDER BY user_id, date, policy_revision DESC
        )
        UPDATE learner_daily_activity a SET
            active_ms=t.active_ms,
            goal_met=(a.goal_minutes > 0 AND t.active_ms >= a.goal_minutes * 60000)
        FROM totals t, newest n
        WHERE a.user_id=t.user_id AND a.date=t.date
          AND n.user_id=a.user_id AND n.date=a.date AND n.policy_revision=a.policy_revision
    ''')
    op.execute('''DELETE FROM learner_daily_activity a USING learner_daily_activity b
        WHERE a.user_id=b.user_id AND a.date=b.date AND a.policy_revision < b.policy_revision''')
    op.execute("ALTER TABLE learner_daily_activity DROP CONSTRAINT learner_daily_activity_pkey")
    op.execute("ALTER TABLE learner_daily_activity DROP COLUMN policy_revision")
    op.execute("ALTER TABLE learner_daily_activity ADD CONSTRAINT learner_daily_activity_pkey PRIMARY KEY (user_id, date)")
