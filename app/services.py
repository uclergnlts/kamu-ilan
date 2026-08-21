from __future__ import annotations

import asyncio
import hashlib
import json

import httpx

from app.adapters import (
    IlanGovTrAdapter,
    InstitutionAnnouncementAdapter,
    IskurAdapter,
    KariyerKapisiAdapter,
    OsymAdapter,
    ResmiGazeteAdapter,
    YokAcademicAdapter,
)
from app.adapters.base import SourceAdapter, SourceProbe
from app.config import Settings
from app.schemas import NormalizedListing


def listing_fingerprint(listing: NormalizedListing) -> str:
    payload = listing.model_dump(mode="json", exclude={"source_key", "external_id"})
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def probe_sources(settings: Settings) -> list[SourceProbe]:
    headers = {"User-Agent": settings.user_agent}
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        adapters = build_adapters(client, settings)
        return list(await asyncio.gather(*(adapter.probe() for adapter in adapters)))


def build_adapters(client: httpx.AsyncClient, settings: Settings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    configured = (
        (settings.ilan_gov_tr_enabled, IlanGovTrAdapter),
        (settings.kariyer_kapisi_enabled, KariyerKapisiAdapter),
        (settings.iskur_enabled, IskurAdapter),
        (settings.osym_enabled, OsymAdapter),
        (settings.resmi_gazete_enabled, ResmiGazeteAdapter),
        (settings.yok_enabled, YokAcademicAdapter),
    )
    adapters.extend(adapter(client) for enabled, adapter in configured if enabled)
    adapters.extend(
        InstitutionAnnouncementAdapter(
            client,
            key=source.key,
            name=source.name,
            public_url=str(source.url),
        )
        for source in settings.institution_sources
        if source.enabled
    )
    return adapters
