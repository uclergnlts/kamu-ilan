from app.adapters.base import SourceAdapter
from app.schemas import NormalizedListing


class InstitutionAnnouncementAdapter(SourceAdapter):
    """Yapılandırmayla eklenen bakanlık, belediye veya üniversite duyuru kaynağı."""

    def __init__(self, client, *, key: str, name: str, public_url: str):
        super().__init__(client)
        self.key = f"institution:{key}"
        self.name = name
        self.public_url = public_url

    async def fetch(self) -> list[NormalizedListing]:
        raise NotImplementedError(
            f"{self.name} için kuruma özel ayrıştırıcı tanımlanmadan "
            "veri toplama etkinleştirilemez."
        )
