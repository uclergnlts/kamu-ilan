from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from hmac import compare_digest
from typing import Annotated
from zoneinfo import ZoneInfo

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import KariyerKapisiAdapter
from app.config import get_settings
from app.db import Base, engine, get_db
from app.digest import prepare_digest, render_digest, send_daily_digest
from app.filtering import listing_matches
from app.models import Listing, Source, UserFilter
from app.scanner import scan_kariyer_kapisi
from app.scheduler import build_scheduler
from app.schemas import NormalizedListing, StoredListing, UserFilterRead, UserFilterUpsert
from app.services import probe_sources


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    scheduler = build_scheduler(settings) if settings.scheduler_enabled else None
    if scheduler:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


app = FastAPI(title="IlanDetect", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/sources/status")
async def source_status() -> dict:
    probes = await probe_sources(get_settings())
    return {
        "status": "ok" if all(item.ok for item in probes) else "degraded",
        "sources": [item.__dict__ for item in probes],
    }


@app.get("/api/v1/listings/sample", response_model=list[NormalizedListing])
async def sample_listings(limit: int = Query(default=10, ge=1, le=50)):
    settings = get_settings()
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent},
        timeout=httpx.Timeout(settings.request_timeout_seconds),
        follow_redirects=True,
    ) as client:
        listings = await KariyerKapisiAdapter(client).fetch_enriched(limit)
    return listings


@app.post("/api/v1/scans/kariyer-kapisi")
async def run_kariyer_scan(
    session: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=10, ge=1, le=50),
):
    return await scan_kariyer_kapisi(session, get_settings(), limit=limit)


@app.get("/api/v1/listings", response_model=list[StoredListing])
def stored_listings(
    session: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = session.execute(
        select(Listing, Source.key)
        .join(Source, Source.id == Listing.source_id)
        .order_by(Listing.published_at.desc(), Listing.id.desc())
        .limit(limit)
    ).all()
    return [
        _stored_listing(listing, source_key)
        for listing, source_key in rows
    ]


@app.put("/api/v1/user-filter", response_model=UserFilterRead)
def save_user_filter(
    payload: UserFilterUpsert,
    session: Annotated[Session, Depends(get_db)],
):
    filters = session.scalar(select(UserFilter).limit(1))
    if filters is None:
        filters = UserFilter(**payload.model_dump())
        session.add(filters)
    else:
        for field, value in payload.model_dump().items():
            setattr(filters, field, value)
    session.commit()
    session.refresh(filters)
    return filters


@app.get("/api/v1/user-filter", response_model=UserFilterRead)
def read_user_filter(session: Annotated[Session, Depends(get_db)]):
    return session.scalar(select(UserFilter).limit(1))


@app.get("/api/v1/listings/matches", response_model=list[StoredListing])
def matching_listings(
    session: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
):
    filters = session.scalar(select(UserFilter).limit(1))
    if filters is None:
        return []
    rows = session.execute(
        select(Listing, Source.key)
        .join(Source, Source.id == Listing.source_id)
        .order_by(Listing.published_at.desc(), Listing.id.desc())
    ).all()
    return [
        _stored_listing(listing, source_key)
        for listing, source_key in rows
        if listing_matches(listing, filters)
    ][:limit]


@app.get("/api/v1/digest/preview")
def digest_preview(session: Annotated[Session, Depends(get_db)]):
    filters = session.scalar(select(UserFilter).limit(1))
    if filters is None:
        return {"status": "skipped", "reason": "user_filter_missing"}
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    content = prepare_digest(session, filters, today=today)
    subject, html = render_digest(content, today=today)
    return {
        "status": "preview",
        "subject": subject,
        "html": html,
        "counts": {
            "new": len(content.new),
            "updated": len(content.updated),
            "expiring": len(content.expiring),
        },
    }


@app.post("/api/v1/digest/send")
async def send_digest(session: Annotated[Session, Depends(get_db)]):
    return await send_daily_digest(session, get_settings())


@app.post("/api/v1/jobs/daily")
async def run_daily_job(
    session: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
):
    settings = get_settings()
    expected = f"Bearer {settings.cron_secret}" if settings.cron_secret else None
    if expected is None or authorization is None or not compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Geçersiz cron yetkilendirmesi")
    scan = await scan_kariyer_kapisi(
        session, settings, limit=settings.daily_scan_limit
    )
    digest = await send_daily_digest(session, settings)
    return {"status": "ok", "scan": scan, "digest": digest}


def _stored_listing(listing: Listing, source_key: str) -> StoredListing:
    return StoredListing(
        id=listing.id,
        source=source_key,
        external_id=listing.external_id,
        institution=listing.institution,
        position=listing.position,
        positions=listing.positions,
        category=listing.category,
        cities=listing.cities,
        quota=listing.quota,
        education=listing.education,
        kpss_required=listing.kpss_required,
        kpss_types=listing.kpss_types,
        published_at=listing.published_at,
        application_start=listing.application_start,
        application_end=listing.application_end,
        official_url=listing.official_url,
        application_url=listing.application_url,
        first_seen_at=listing.first_seen_at,
        last_seen_at=listing.last_seen_at,
    )
