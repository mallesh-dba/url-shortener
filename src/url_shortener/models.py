from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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
class ClickEvent(Base):
    __tablename__ = "click_events"
    __table_args__ = (
        Index(
            "ix_click_events_code_clicked_at",
            "code",
            text("clicked_at DESC"),
        ),
    )

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("short_links.code"),
        nullable=False,
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ProcessedClickEvent(Base):
    __tablename__ = "processed_click_event_ids"
    __table_args__ = (
        Index("ix_processed_click_event_ids_processed_at", "processed_at"),
    )

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DailyClickAggregate(Base):
    __tablename__ = "daily_click_aggregates"
    __table_args__ = (
        CheckConstraint("clicks_total > 0", name="ck_daily_click_aggregates_positive"),
    )

    link_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("short_links.id"),
        primary_key=True,
    )
    bucket_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
    )
    clicks_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
