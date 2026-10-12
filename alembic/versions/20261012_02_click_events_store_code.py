"""Store the short-link code rather than the internal link ID in click events.

Revision ID: 20261012_02
Revises: 20261012_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261012_02"
down_revision: str | None = "20261012_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_click_events_link_id_clicked_at",
        table_name="click_events",
    )
    op.drop_constraint(
        "click_events_link_id_fkey",
        "click_events",
        type_="foreignkey",
    )
    op.add_column(
        "click_events",
        sa.Column("code", sa.String(length=16), nullable=True),
    )
    op.execute(
        """
        UPDATE click_events
        SET code = short_links.code
        FROM short_links
        WHERE click_events.link_id = short_links.id
        """
    )
    op.alter_column("click_events", "code", nullable=False)
    op.create_foreign_key(
        "fk_click_events_code_short_links",
        "click_events",
        "short_links",
        ["code"],
        ["code"],
    )
    op.drop_column("click_events", "link_id")
    op.create_index(
        "ix_click_events_code_clicked_at",
        "click_events",
        ["code", sa.text("clicked_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_click_events_code_clicked_at",
        table_name="click_events",
    )
    op.drop_constraint(
        "fk_click_events_code_short_links",
        "click_events",
        type_="foreignkey",
    )
    op.add_column(
        "click_events",
        sa.Column("link_id", sa.BigInteger(), nullable=True),
    )
    op.execute(
        """
        UPDATE click_events
        SET link_id = short_links.id
        FROM short_links
        WHERE click_events.code = short_links.code
        """
    )
    op.alter_column("click_events", "link_id", nullable=False)
    op.create_foreign_key(
        "click_events_link_id_fkey",
        "click_events",
        "short_links",
        ["link_id"],
        ["id"],
    )
    op.drop_column("click_events", "code")
    op.create_index(
        "ix_click_events_link_id_clicked_at",
        "click_events",
        ["link_id", sa.text("clicked_at DESC")],
    )
