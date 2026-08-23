import asyncio
from pathlib import Path

import httpx

from app.adapters.kariyer_kapisi import (
    KariyerKapisiAdapter,
    enrich_listing,
    parse_rss,
)


def test_parse_rss_normalizes_public_fields() -> None:
    content = Path("tests/fixtures/kariyer_kapisi_rss.xml").read_bytes()
    listings = parse_rss(content)

    assert len(listings) == 1
    listing = listings[0]
    assert listing.external_id == "sample-guid"
    assert listing.institution == "ÖRNEK KURUM"
    assert listing.position == "BİLİŞİM PERSONELİ ALIM İLANI"
    assert listing.category == "Sözleşmeli Personel İlanları"
    assert listing.published_at.isoformat() == "2026-08-17T08:00:00+03:00"


def test_enrich_listing_aggregates_verified_detail_fields() -> None:
    listing = parse_rss(Path("tests/fixtures/kariyer_kapisi_rss.xml").read_bytes())[0]
    detail = {
        "kurumAdi": "ÖRNEK KURUM",
        "ilanTuru": "Sözleşmeli Personel İlanları",
        "ilanMetni": "Lisans mezunları için KPSSP3 ve Ön lisans için KPSS P93 aranır.",
        "basTarih": "2026-08-17T08:00:00",
        "bitTarih": "2026-08-31T23:59:00",
        "eDevletteGorunsun": 1,
        "eDevletServisURL": "https://www.turkiye.gov.tr/ornek-basvuru",
    }
    positions = [
        {
            "unvan": "MÜHENDİS",
            "kontenjanList": [{"il": "ANKARA", "kontenjan": 2}],
            "degerlemeAsamaList": [{"turu": "KPSS"}],
        },
        {
            "unvan": "TEKNİKER",
            "kontenjanList": [{"il": "İSTANBUL", "kontenjan": 3}],
            "degerlemeAsamaList": [],
        },
    ]

    enriched = enrich_listing(listing, detail, positions)

    assert enriched.positions == ["MÜHENDİS", "TEKNİKER"]
    assert enriched.cities == ["ANKARA", "İSTANBUL"]
    assert enriched.quota == 5
    assert enriched.kpss_required is True
    assert enriched.kpss_types == ["P3", "P93"]
    assert enriched.education == ["Ön lisans", "Lisans"]
    assert enriched.application_end.isoformat() == "2026-08-31"


def test_fetch_enriched_falls_back_to_rss_when_detail_api_times_out() -> None:
    listing = parse_rss(Path("tests/fixtures/kariyer_kapisi_rss.xml").read_bytes())[0]

    class TimeoutClient:
        async def post(self, url: str, **kwargs):
            request = httpx.Request("POST", url)
            raise httpx.ConnectTimeout("connection timed out", request=request)

    class FixtureAdapter(KariyerKapisiAdapter):
        async def fetch(self):
            return [listing]

    result = asyncio.run(FixtureAdapter(TimeoutClient()).fetch_enriched(limit=1))

    assert result == [listing]
