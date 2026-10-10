from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime


class Base(DeclarativeBase):
    pass


class ShortLink(Base):
    __tablename__ = "short_links"
    __table_args__ = (
        UniqueConstraint("code", name="uq_short_links_code"),
        CheckConstraint(
            "clicks_total >= 0",
            name="ck_short_links_clicks_total_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    destination_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    clicks_total: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )


class ClickEvent(Base):
    __tablename__ = "click_events"
    __table_args__ = (
        Index(
            "ix_click_events_link_id_clicked_at",
            "link_id",
            text("clicked_at DESC"),
        ),
    )

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    link_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("short_links.id"),
        nullable=False,
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
