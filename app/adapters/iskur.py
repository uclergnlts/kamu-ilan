from app.adapters.base import SourceAdapter
from app.schemas import NormalizedListing


class IskurAdapter(SourceAdapter):
    key = "iskur"
    name = "İŞKUR Kamu İşçi İlanları"
    public_url = "https://acikisharita.iskur.gov.tr/"
    search_url = "https://esube.iskur.gov.tr/Istihdam/AcikIsIlanAra.aspx"

    async def fetch(self) -> list[NormalizedListing]:
        raise NotImplementedError(
            "Kamu işyeri filtresi ve açık ilan veri sözleşmesi doğrulandıktan "
            "sonra etkinleştirilecek."
        )
