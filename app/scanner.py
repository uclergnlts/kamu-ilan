from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx
from sqlalchemy.orm import Session

from app.adapters import KariyerKapisiAdapter
from app.config import Settings
from app.models import ScanRun, ScanStatus, utcnow
from app.persistence import get_or_create_source, upsert_listing


@dataclass
class ScanSummary:
    scan_id: int
    source: str
    fetched: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0


async def scan_kariyer_kapisi(
    session: Session, settings: Settings, *, limit: int
) -> ScanSummary:
    scan = ScanRun(status=ScanStatus.running, source_results={})
    session.add(scan)
    session.commit()
    session.refresh(scan)
    summary = ScanSummary(scan_id=scan.id, source="kariyer_kapisi")

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
        ) as client:
            adapter = KariyerKapisiAdapter(client)
            listings = await adapter.fetch_enriched(limit)

        source = get_or_create_source(
            session,
            key=adapter.key,
            name=adapter.name,
            base_url=adapter.public_url,
        )
        for listing in listings:
            result = upsert_listing(session, source, listing)
            summary.fetched += 1
            setattr(summary, result.state, getattr(summary, result.state) + 1)

        source.last_success_at = utcnow()
        source.last_error = None
        scan.status = ScanStatus.succeeded
        scan.finished_at = utcnow()
        scan.source_results = asdict(summary)
        session.commit()
        return summary
    except Exception as exc:
        session.rollback()
        failed_scan = session.get(ScanRun, scan.id)
        if failed_scan is not None:
            failed_scan.status = ScanStatus.failed
            failed_scan.finished_at = utcnow()
            failed_scan.error = str(exc)[:2000]
            failed_scan.source_results = asdict(summary)
            session.commit()
        raise
