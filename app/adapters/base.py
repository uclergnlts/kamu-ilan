from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.schemas import NormalizedListing


@dataclass(frozen=True)
class SourceProbe:
    key: str
    name: str
    ok: bool
    url: str
    status_code: int | None = None
    detail: str | None = None


class SourceAdapter(ABC):
    key: str
    name: str
    public_url: str

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def probe(self) -> SourceProbe:
        try:
            response = await self.client.get(self.public_url)
            response.raise_for_status()
            return SourceProbe(self.key, self.name, True, self.public_url, response.status_code)
        except httpx.HTTPError as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            return SourceProbe(self.key, self.name, False, self.public_url, status, str(exc))

    @abstractmethod
    async def fetch(self) -> list[NormalizedListing]:
        """Fetch and normalize current listings."""
