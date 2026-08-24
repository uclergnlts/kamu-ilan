from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from hmac import compare_digest
from typing import Annotated
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters import KariyerKapisiAdapter
from app.config import get_settings
from app.db import Base, engine, ensure_schema, get_db
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
    ensure_schema()
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


@app.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_form() -> str:
    return _unsubscribe_page()


@app.post("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> str:
    form = parse_qs((await request.body()).decode("utf-8"))
    email = form.get("email", [""])[0].strip().casefold()
    if email:
        filters = session.scalar(select(UserFilter).where(func.lower(UserFilter.email) == email))
        if filters is not None:
            filters.subscribed = False
            session.commit()
    return _unsubscribe_page(completed=True)


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
    return [_stored_listing(listing, source_key) for listing, source_key in rows]


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
    settings = get_settings()
    subject, html = render_digest(
        content,
        today=today,
        unsubscribe_url=f"{settings.public_base_url.rstrip('/')}/unsubscribe",
    )
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
    scan = await scan_kariyer_kapisi(session, settings, limit=settings.daily_scan_limit)
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


def _unsubscribe_page(*, completed: bool = False) -> str:
    if completed:
        content = """
          <div class="icon">✓</div>
          <h1>Talebiniz alındı</h1>
          <p>Adres kayıtlıysa kamu ilanı e-postaları durduruldu.</p>
        """
    else:
        content = """
          <div class="brand">ILANDETECT</div>
          <h1>Abonelikten çık</h1>
          <p>E-posta adresinizi girerek günlük kamu ilanı bildirimlerini durdurabilirsiniz.</p>
          <form method="post" action="/unsubscribe">
            <label for="email">E-posta adresi</label>
            <input id="email" name="email" type="email" autocomplete="email" required
                   placeholder="ornek@email.com">
            <button type="submit">Aboneliği sonlandır</button>
          </form>
        """
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Abonelikten çık - IlanDetect</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f1f5f9;color:#0f172a;font-family:Arial,sans-serif}}
.wrap{{min-height:100vh;display:grid;place-items:center;padding:24px}}
.card{{width:100%;max-width:480px;background:#fff;border:1px solid #e2e8f0;
border-radius:18px;padding:34px;box-shadow:0 12px 35px rgba(15,23,42,.08)}}
.brand{{font-size:12px;letter-spacing:1.4px;font-weight:800;color:#2563eb}}
h1{{font-size:27px;margin:10px 0}}
p{{color:#64748b;line-height:1.6}}
label{{display:block;font-size:13px;font-weight:700;margin:24px 0 8px}}
input{{width:100%;border:1px solid #cbd5e1;border-radius:10px;padding:13px;font-size:16px}}
button{{width:100%;border:0;border-radius:10px;padding:13px;margin-top:12px;
background:#dc2626;color:#fff;font-size:15px;font-weight:700;cursor:pointer}}
.icon{{width:52px;height:52px;border-radius:50%;display:grid;place-items:center;
background:#dcfce7;color:#15803d;font-size:26px;font-weight:800}}
</style></head><body><main class="wrap"><section class="card">
{content}
</section></main></body></html>"""
