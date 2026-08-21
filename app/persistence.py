from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, ListingChange, Source, utcnow
from app.schemas import NormalizedListing
from app.services import listing_fingerprint

LISTING_FIELDS = (
    "institution",
    "position",
    "positions",
    "category",
    "cities",
    "quota",
    "education",
    "kpss_required",
    "kpss_types",
    "published_at",
    "application_start",
    "application_end",
    "text",
    "official_url",
    "application_url",
    "image_url",
)


@dataclass(frozen=True)
class UpsertResult:
    listing: Listing
    state: str
    changed_fields: list[str]


def get_or_create_source(
    session: Session, *, key: str, name: str, base_url: str
) -> Source:
    source = session.scalar(select(Source).where(Source.key == key))
    if source is None:
        source = Source(key=key, name=name, base_url=base_url, enabled=True)
        session.add(source)
        session.flush()
    else:
        source.name = name
        source.base_url = base_url
    return source


def upsert_listing(
    session: Session, source: Source, incoming: NormalizedListing
) -> UpsertResult:
    listing = session.scalar(
        select(Listing).where(
            Listing.source_id == source.id,
            Listing.external_id == incoming.external_id,
        )
    )
    values = _model_values(incoming)
    fingerprint = listing_fingerprint(incoming)
    now = utcnow()
    if listing is None:
        listing = Listing(
            source_id=source.id,
            external_id=incoming.external_id,
            fingerprint=fingerprint,
            first_seen_at=now,
            last_seen_at=now,
            **values,
        )
        session.add(listing)
        session.flush()
        return UpsertResult(listing, "new", [])

    listing.last_seen_at = now
    if listing.fingerprint == fingerprint:
        return UpsertResult(listing, "unchanged", [])

    changed_fields = [
        field for field, value in values.items() if getattr(listing, field) != value
    ]
    old_fingerprint = listing.fingerprint
    for field, value in values.items():
        setattr(listing, field, value)
    listing.fingerprint = fingerprint
    session.add(
        ListingChange(
            listing_id=listing.id,
            old_fingerprint=old_fingerprint,
            new_fingerprint=fingerprint,
            changed_fields=changed_fields,
        )
    )
    return UpsertResult(listing, "updated", changed_fields)


def _model_values(listing: NormalizedListing) -> dict:
    data = listing.model_dump(mode="python")
    return {
        field: str(data[field]) if field.endswith("_url") and data[field] else data[field]
        for field in LISTING_FIELDS
    }
