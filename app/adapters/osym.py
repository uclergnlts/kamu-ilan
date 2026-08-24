from app.adapters.base import SourceAdapter
from app.schemas import NormalizedListing


class OsymAdapter(SourceAdapter):
    key = "osym"
    name = "ÖSYM KPSS Tercih Duyuruları"
    public_url = "https://www.osym.gov.tr/SinavGrubu/Index/3"

    async def fetch(self) -> list[NormalizedListing]:
        raise NotImplementedError(
            "KPSS tercih duyurusu ve kadro tablosu ayrıştırıcıları tamamlanınca etkinleştirilecek."
        )
