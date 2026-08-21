from app.adapters.base import SourceAdapter
from app.schemas import NormalizedListing


class IlanGovTrAdapter(SourceAdapter):
    key = "ilan_gov_tr"
    name = "ilan.gov.tr"
    public_url = "https://www.ilan.gov.tr/ilan/tum-ilanlar/personel-alimi"
    daily_sitemap_url = "https://www.ilan.gov.tr/sitemap/daily-ads.xml"

    async def fetch(self) -> list[NormalizedListing]:
        raise NotImplementedError(
            "Parser, kullanım izni ve ilan kategori kapsamı doğrulandıktan sonra etkinleştirilecek."
        )

