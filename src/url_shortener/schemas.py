import re
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

RESERVED_SHORT_CODES = frozenset(
    {"api", "health", "metrics", "docs", "redoc", "openapi.json"}
)


class ShortLinkCreateRequest(BaseModel):
    destination_url: AnyHttpUrl
    custom_alias: str | None = Field(default=None, min_length=3, max_length=16)

    @field_validator("destination_url", mode="before")
    @classmethod
    def require_absolute_http_url(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                parsed = urlsplit(value)
                hostname = parsed.hostname
                parsed.port
            except ValueError as error:
                raise ValueError(
                    "destination_url must be an absolute HTTP(S) URL"
                ) from error
            if (
                parsed.scheme.lower() not in {"http", "https"}
                or not parsed.netloc
                or not hostname
            ):
                raise ValueError(
                    "destination_url must be an absolute HTTP(S) URL"
                )
        return value

    @field_validator("custom_alias")
    @classmethod
    def validate_custom_alias(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", value) is None:
            raise ValueError(
                "custom_alias must contain lowercase ASCII letters, digits, "
                "or hyphens and start and end with a letter or digit"
            )
        if value in RESERVED_SHORT_CODES:
            raise ValueError("custom_alias is reserved")
        return value


class ShortLinkCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    short_url: AnyHttpUrl
    created_at: datetime


class LinkAnalyticsResponse(BaseModel):
    code: str
    clicks_total: int = Field(ge=0)
