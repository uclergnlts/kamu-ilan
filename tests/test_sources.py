import httpx

from app.config import InstitutionSourceSettings, Settings
from app.services import build_adapters


def test_default_source_registry_contains_six_official_sources() -> None:
    settings = Settings(_env_file=None)
    with httpx.Client() as sync_client:
        # Bağdaştırıcılar yalnız istemciyi saklar; bu test ağ isteği yapmaz.
        adapters = build_adapters(sync_client, settings)  # type: ignore[arg-type]

    assert [adapter.key for adapter in adapters] == [
        "ilan_gov_tr",
        "kariyer_kapisi",
        "iskur",
        "osym",
        "resmi_gazete",
        "yok_academic",
    ]


def test_configured_institution_source_is_added() -> None:
    settings = Settings(
        _env_file=None,
        institution_sources=[
            InstitutionSourceSettings(
                key="adalet",
                name="Adalet Bakanlığı",
                url="https://www.adalet.gov.tr/duyurular",
            )
        ],
    )
    with httpx.Client() as sync_client:
        adapters = build_adapters(sync_client, settings)  # type: ignore[arg-type]

    assert adapters[-1].key == "institution:adalet"
