"""Add bounded analytics retention and rolling aggregate storage.

Revision ID: 20261012_01
Revises: 20261010_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261012_01"
down_revision: str | None = "20261010_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_click_event_ids",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_processed_click_event_ids_processed_at",
        "processed_click_event_ids",
        ["processed_at"],
    )
    op.create_table(
        "daily_click_aggregates",
        sa.Column("link_id", sa.BigInteger(), nullable=False),
        sa.Column("bucket_date", sa.Date(), nullable=False),
        sa.Column("clicks_total", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "clicks_total > 0",
            name="ck_daily_click_aggregates_positive",
        ),
        sa.ForeignKeyConstraint(["link_id"], ["short_links.id"]),
        sa.PrimaryKeyConstraint("link_id", "bucket_date"),
    )
    op.execute(
        """
        INSERT INTO processed_click_event_ids (event_id, processed_at)
        SELECT event_id, now()
        FROM click_events
        ON CONFLICT (event_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO daily_click_aggregates (link_id, bucket_date, clicks_total)
        SELECT id, (now() AT TIME ZONE 'UTC')::date, clicks_total
        FROM short_links
        WHERE clicks_total > 0
        """
    )
    op.drop_constraint(
        "ck_short_links_clicks_total_nonnegative",
        "short_links",
        type_="check",
    )
    op.drop_column("short_links", "clicks_total")


def downgrade() -> None:
    op.add_column(
        "short_links",
        sa.Column(
            "clicks_total",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE short_links
        SET clicks_total = COALESCE(
            (
                SELECT sum(daily_click_aggregates.clicks_total)
                FROM daily_click_aggregates
                WHERE daily_click_aggregates.link_id = short_links.id
            ),
            0
        )
        """
    )
    op.create_check_constraint(
        "ck_short_links_clicks_total_nonnegative",
        "short_links",
        "clicks_total >= 0",
    )
    op.drop_table("daily_click_aggregates")
    op.drop_index(
        "ix_processed_click_event_ids_processed_at",
        table_name="processed_click_event_ids",
    )
    op.drop_table("processed_click_event_ids")
