from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import httpx

from app.adapters.base import SourceAdapter
from app.schemas import NormalizedListing

logger = logging.getLogger(__name__)


class KariyerKapisiAdapter(SourceAdapter):
    key = "kariyer_kapisi"
    name = "Kariyer Kapısı"
    public_url = "https://kariyerkapisi.gov.tr/isealim"
    rss_url = "https://kariyerkapisi.gov.tr/RSS"
    api_url = "https://api.kariyerkapisi.gov.tr/api"

    async def fetch(self) -> list[NormalizedListing]:
        response = await self.client.get(self.rss_url)
        response.raise_for_status()
        return parse_rss(response.content)

    async def fetch_enriched(self, limit: int) -> list[NormalizedListing]:
        listings = (await self.fetch())[:limit]
        semaphore = asyncio.Semaphore(4)
        enrichment_unavailable = asyncio.Event()

        async def enrich(listing: NormalizedListing) -> NormalizedListing:
            async with semaphore:
                if enrichment_unavailable.is_set():
                    return listing
                try:
                    return await self.enrich(listing)
                except httpx.HTTPError as exc:
                    enrichment_unavailable.set()
                    logger.warning(
                        "Kariyer Kapisi detail API unavailable; continuing with RSS data: %s",
                        exc,
                    )
                    return listing

        return list(await asyncio.gather(*(enrich(listing) for listing in listings)))

    async def enrich(self, listing: NormalizedListing) -> NormalizedListing:
        payload = {"ilanGuid": listing.external_id}
        headers = {
            "Origin": "https://kariyerkapisi.gov.tr",
            "Referer": str(listing.official_url),
        }
        detail_response, positions_response = await asyncio.gather(
            self.client.post(
                f"{self.api_url}/ilan/GetIlanPreviewPublic", json=payload, headers=headers
            ),
            self.client.post(
                f"{self.api_url}/altilan/GetAltIlanInfoByIlanIdPublic",
                json=payload,
                headers=headers,
            ),
        )
        detail_response.raise_for_status()
        positions_response.raise_for_status()
        return enrich_listing(listing, detail_response.json(), positions_response.json())


def parse_rss(content: bytes) -> list[NormalizedListing]:
    root = ElementTree.fromstring(content.decode("utf-8-sig"))
    listings = []
    for item in root.findall("./channel/item"):
        title = _text(item, "title")
        link = _text(item, "link")
        guid = _text(item, "guid") or link
        institution, position = _split_title(title)
        enclosure = item.find("enclosure")
        image_url = enclosure.get("url") if enclosure is not None else None
        listings.append(
            NormalizedListing(
                source_key="kariyer_kapisi",
                external_id=_external_id(guid),
                institution=institution,
                position=position,
                category=_text(item, "category") or None,
                published_at=_published_at(_text(item, "pubDate")),
                text=_text(item, "description") or None,
                official_url=link,
                application_url=link,
                image_url=image_url,
            )
        )
    return listings


def _text(item: ElementTree.Element, tag: str) -> str:
    return (item.findtext(tag) or "").strip()


def _split_title(title: str) -> tuple[str | None, str]:
    institution, separator, position = title.partition(" - ")
    if not separator:
        return None, title
    return institution.strip(), position.strip()


def _external_id(guid: str) -> str:
    values = parse_qs(urlparse(guid).query).get("i")
    return values[0] if values else guid


def _published_at(value: str):
    return parsedate_to_datetime(value) if value else None


def enrich_listing(
    listing: NormalizedListing, detail: dict, position_details: list[dict]
) -> NormalizedListing:
    cities = sorted(
        {
            quota["il"].strip()
            for position in position_details
            for quota in position.get("kontenjanList", [])
            if quota.get("il")
        }
    )
    quota = sum(
        int(item.get("kontenjan", 0) or 0)
        for position in position_details
        for item in position.get("kontenjanList", [])
    )
    positions = list(
        dict.fromkeys(
            position.get("unvan", "").strip()
            for position in position_details
            if position.get("unvan", "").strip()
        )
    )
    raw_text = "\n".join(
        [detail.get("ilanMetni", "")]
        + [position.get("ilanMetni", "") for position in position_details]
    )
    kpss_types = sorted(set(re.findall(r"KPSS\s*P(?:UAN)?\s*(\d{1,3})", raw_text, re.I)))
    kpss_types = [f"P{value}" for value in kpss_types]
    has_kpss_stage = any(
        stage.get("turu", "").upper() == "KPSS"
        for position in position_details
        for stage in position.get("degerlemeAsamaList", [])
    )
    education = [
        level
        for level in ("İlköğretim", "Ortaöğretim", "Ön lisans", "Lisans", "Yüksek lisans")
        if level.casefold() in raw_text.casefold()
    ]
    application_url = (
        detail.get("eDevletServisURL")
        if detail.get("eDevletteGorunsun")
        else detail.get("basvuruLinki")
    )
    return listing.model_copy(
        update={
            "institution": detail.get("kurumAdi") or listing.institution,
            "category": detail.get("ilanTuru") or listing.category,
            "positions": positions,
            "cities": cities,
            "quota": quota or detail.get("kontenjan") or None,
            "education": education,
            "kpss_required": has_kpss_stage or bool(kpss_types),
            "kpss_types": kpss_types,
            "application_start": _iso_date(detail.get("basTarih")),
            "application_end": _iso_date(detail.get("bitTarih")),
            "application_url": application_url or listing.application_url,
        }
    )


def _iso_date(value: str | None):
    return datetime.fromisoformat(value).date() if value else None
