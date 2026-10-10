from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="URL_SHORTENER_",
        env_file=".env",
        extra="ignore",
    )

    database_url: SecretStr
    redis_url: SecretStr
    public_base_url: AnyHttpUrl
    db_pool_size: Annotated[int, Field(gt=0)] = 10
    db_max_overflow: Annotated[int, Field(ge=0)] = 20
    db_pool_timeout_seconds: Annotated[float, Field(gt=0)] = 5
    db_connect_timeout_seconds: Annotated[float, Field(gt=0)] = 5
    db_readiness_timeout_seconds: Annotated[float, Field(gt=0)] = 2
    redis_max_connections: Annotated[int, Field(gt=0)] = 50
    redis_connect_timeout_seconds: Annotated[float, Field(gt=0)] = 2
    redis_socket_timeout_seconds: Annotated[float, Field(gt=0)] = 2
    link_cache_ttl_seconds: Annotated[int, Field(gt=0)] = 3600

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        parsed = urlsplit(value.get_secret_value())
        if parsed.scheme != "postgresql+asyncpg" or not parsed.hostname:
            raise ValueError(
                "database_url must be a PostgreSQL URL using the asyncpg driver"
            )
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr) -> SecretStr:
        parsed = urlsplit(value.get_secret_value())
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("redis_url must be a redis:// or rediss:// URL")
        return value

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        parsed = urlsplit(str(value))
        if (
            parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError(
                "public_base_url must be an HTTP(S) origin without credentials, "
                "path, query, or fragment"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
