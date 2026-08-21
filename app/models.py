from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class ScanStatus(str, enum.Enum):
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    institution: Mapped[Optional[str]] = mapped_column(String(300))
    position: Mapped[str] = mapped_column(String(500))
    positions: Mapped[list[str]] = mapped_column(JSON, default=list)
    category: Mapped[Optional[str]] = mapped_column(String(200))
    cities: Mapped[list[str]] = mapped_column(JSON, default=list)
    quota: Mapped[Optional[int]] = mapped_column(Integer)
    education: Mapped[list[str]] = mapped_column(JSON, default=list)
    kpss_required: Mapped[Optional[bool]] = mapped_column(Boolean)
    kpss_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    application_start: Mapped[Optional[date]] = mapped_column(Date)
    application_end: Mapped[Optional[date]] = mapped_column(Date, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    text: Mapped[Optional[str]] = mapped_column(Text)
    official_url: Mapped[str] = mapped_column(String(1000))
    application_url: Mapped[Optional[str]] = mapped_column(String(1000))
    image_url: Mapped[Optional[str]] = mapped_column(String(1000))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ListingChange(Base):
    __tablename__ = "listing_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    old_fingerprint: Mapped[str] = mapped_column(String(64))
    new_fingerprint: Mapped[str] = mapped_column(String(64))
    changed_fields: Mapped[list[str]] = mapped_column(JSON, default=list)


class UserFilter(Base):
    __tablename__ = "user_filters"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    send_hour: Mapped[int] = mapped_column(Integer, default=8)
    cities: Mapped[list[str]] = mapped_column(JSON, default=list)
    include_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    education_levels: Mapped[list[str]] = mapped_column(JSON, default=list)
    kpss_required: Mapped[Optional[bool]] = mapped_column(Boolean)
    kpss_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    institutions: Mapped[list[str]] = mapped_column(JSON, default=list)
    deadline_days: Mapped[Optional[int]] = mapped_column(Integer)
    send_empty_digest: Mapped[bool] = mapped_column(Boolean, default=False)


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_filter_id: Mapped[int] = mapped_column(ForeignKey("user_filters.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    provider_id: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    listing_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    error: Mapped[Optional[str]] = mapped_column(Text)


class ScanRun(Base):
    __tablename__ = "scan_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.running)
    source_results: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text)
