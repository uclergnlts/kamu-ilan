from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, HttpUrl


class NormalizedListing(BaseModel):
    source_key: str
    external_id: str
    institution: str | None = None
    position: str
    positions: list[str] = Field(default_factory=list)
    category: str | None = None
    cities: list[str] = Field(default_factory=list)
    quota: int | None = None
    education: list[str] = Field(default_factory=list)
    kpss_required: bool | None = None
    kpss_types: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    application_start: date | None = None
    application_end: date | None = None
    text: str | None = None
    official_url: HttpUrl
    application_url: HttpUrl | None = None
    image_url: HttpUrl | None = None


class StoredListing(BaseModel):
    id: int
    source: str
    external_id: str
    institution: str | None
    position: str
    positions: list[str]
    category: str | None
    cities: list[str]
    quota: int | None
    education: list[str]
    kpss_required: bool | None
    kpss_types: list[str]
    published_at: datetime | None
    application_start: date | None
    application_end: date | None
    official_url: str
    application_url: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class UserFilterUpsert(BaseModel):
    email: str
    send_hour: int = Field(default=8, ge=0, le=23)
    cities: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    education_levels: list[str] = Field(default_factory=list)
    kpss_required: bool | None = None
    kpss_types: list[str] = Field(default_factory=list)
    institutions: list[str] = Field(default_factory=list)
    deadline_days: int | None = Field(default=None, ge=0)
    send_empty_digest: bool = False


class UserFilterRead(UserFilterUpsert):
    id: int
    subscribed: bool
