from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex
from sqlalchemy.sql.elements import TextClause

from url_shortener.models import Base, ClickEvent, ShortLink


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
    assert check_constraints == {
        "ck_short_links_clicks_total_nonnegative": "clicks_total >= 0"
    }
    assert table.c.created_at.server_default is not None
    assert table.c.clicks_total.server_default is not None
    assert table.c.destination_url.nullable is False


def test_click_event_schema_has_uuid_key_foreign_key_and_descending_index() -> None:
    table = ClickEvent.__table__
    event_id_type = table.c.event_id.type
    link_foreign_key = next(iter(table.c.link_id.foreign_keys))
    index = next(iter(table.indexes))
    compiled_index = str(CreateIndex(index).compile(dialect=postgresql.dialect()))

    assert event_id_type.as_uuid is True
    assert table.primary_key.columns.keys() == ["event_id"]
    assert link_foreign_key.target_fullname == "short_links.id"
    assert table.c.link_id.nullable is False
    assert table.c.clicked_at.type.timezone is True
    assert compiled_index.endswith("(link_id, clicked_at DESC)")
    assert isinstance(index.expressions[1], TextClause)
    assert index.expressions[1].text == "clicked_at DESC"
    assert "short_links" in Base.metadata.tables
