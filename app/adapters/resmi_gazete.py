from app.adapters.base import SourceAdapter
from app.schemas import NormalizedListing


class ResmiGazeteAdapter(SourceAdapter):
    key = "resmi_gazete"
    name = "Resmî Gazete"
    public_url = "https://www.resmigazete.gov.tr/"

    async def fetch(self) -> list[NormalizedListing]:
        raise NotImplementedError(
            "Günlük ilan bölümü ve PDF/HTML ayrıştırma sözleşmesi tamamlanınca etkinleştirilecek."
        )
