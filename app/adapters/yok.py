from app.adapters.base import SourceAdapter
from app.schemas import NormalizedListing


class YokAcademicAdapter(SourceAdapter):
    key = "yok_academic"
    name = "YÖK Akademik İlanları"
    public_url = "https://personel.yok.gov.tr/"

    async def fetch(self) -> list[NormalizedListing]:
        raise NotImplementedError(
            "YÖK ve üniversite ilan kapsamı ile mükerrerlik kuralları "
            "doğrulanınca etkinleştirilecek."
        )
