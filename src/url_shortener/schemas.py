from datetime import datetime
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class ShortLinkCreateRequest(BaseModel):
    destination_url: AnyHttpUrl

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


class ShortLinkCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    short_url: AnyHttpUrl
    created_at: datetime


class LinkAnalyticsResponse(BaseModel):
    code: str
    clicks_total: int = Field(ge=0)
