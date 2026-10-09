import pytest
from pydantic import ValidationError

from url_shortener.config import Settings


def valid_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+asyncpg://user:password@localhost/shortener",
        "redis_url": "redis://localhost:6379/0",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_validate_dependency_urls() -> None:
    settings = valid_settings()

    assert settings.database_url.get_secret_value().startswith(
        "postgresql+asyncpg://"
    )
    assert settings.redis_url.get_secret_value().startswith("redis://")
    assert "password" not in repr(settings)


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("database_url", "postgresql://localhost/shortener"),
        ("redis_url", "http://localhost:6379"),
        ("db_pool_size", 0),
        ("redis_max_connections", 0),
    ],
)
def test_settings_reject_invalid_values(setting: str, value: object) -> None:
    with pytest.raises(ValidationError):
        valid_settings(**{setting: value})


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "URL_SHORTENER_DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost/shortener",
    )
    monkeypatch.setenv("URL_SHORTENER_REDIS_URL", "rediss://localhost:6379/0")
    monkeypatch.setenv("URL_SHORTENER_DB_POOL_SIZE", "7")

    settings = Settings(_env_file=None)

    assert settings.db_pool_size == 7
    assert settings.redis_url.get_secret_value().startswith("rediss://")
