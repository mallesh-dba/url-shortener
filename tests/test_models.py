from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex
from sqlalchemy.sql.elements import TextClause

from url_shortener.models import (
    Base,
    ClickEvent,
    DailyClickAggregate,
    ProcessedClickEvent,
    ShortLink,
)


def test_short_link_schema_constraints_and_server_defaults() -> None:
    table = ShortLink.__table__
    unique_constraints = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert table.c.id.identity is not None
    assert table.c.id.identity.always is True
    assert table.c.code.type.length == 16
    assert "uq_short_links_code" in unique_constraints
    assert check_constraints == {}
    assert table.c.created_at.server_default is not None
    assert table.c.destination_url.nullable is False


def test_click_event_schema_has_uuid_key_code_foreign_key_and_index() -> None:
    table = ClickEvent.__table__
    event_id_type = table.c.event_id.type
    code_foreign_key = next(iter(table.c.code.foreign_keys))
    index = next(iter(table.indexes))
    compiled_index = str(CreateIndex(index).compile(dialect=postgresql.dialect()))

    assert event_id_type.as_uuid is True
    assert table.primary_key.columns.keys() == ["event_id"]
    assert code_foreign_key.target_fullname == "short_links.code"
    assert table.c.code.type.length == 16
    assert table.c.code.nullable is False
    assert table.c.clicked_at.type.timezone is True
    assert compiled_index.endswith("(code, clicked_at DESC)")
    assert isinstance(index.expressions[1], TextClause)
    assert index.expressions[1].text == "clicked_at DESC"
    assert "short_links" in Base.metadata.tables


def test_analytics_retention_tables_store_only_event_ids_and_daily_counts() -> None:
    processed_table = ProcessedClickEvent.__table__
    aggregate_table = DailyClickAggregate.__table__

    assert processed_table.columns.keys() == ["event_id", "processed_at"]
    assert aggregate_table.columns.keys() == [
        "link_id",
        "bucket_date",
        "clicks_total",
    ]
    assert aggregate_table.primary_key.columns.keys() == [
        "link_id",
        "bucket_date",
    ]
