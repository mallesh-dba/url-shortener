"""Create short-link and click-event tables.

Revision ID: 20261010_01
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Identity
from sqlalchemy.dialects import postgresql

revision: str = "20261010_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "short_links",
        sa.Column("id", sa.BigInteger(), Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "clicks_total",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "clicks_total >= 0",
            name="ck_short_links_clicks_total_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_short_links_code"),
    )
    op.create_table(
        "click_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", sa.BigInteger(), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["link_id"], ["short_links.id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_click_events_link_id_clicked_at",
        "click_events",
        ["link_id", sa.text("clicked_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_click_events_link_id_clicked_at",
        table_name="click_events",
    )
    op.drop_table("click_events")
    op.drop_table("short_links")
