from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class InstitutionSourceSettings(BaseModel):
    key: str
    name: str
    url: HttpUrl
    enabled: bool = True


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./ilandetect.db"
    timezone: str = "Europe/Istanbul"
    admin_email: str | None = None
    resend_api_key: str | None = None
    email_from: str = "IlanDetect <ilan@ornek.com>"
    public_base_url: str = "https://kamu-ilan.onrender.com"
    ilan_gov_tr_enabled: bool = True
    kariyer_kapisi_enabled: bool = True
    iskur_enabled: bool = True
    osym_enabled: bool = True
    resmi_gazete_enabled: bool = True
    yok_enabled: bool = True
    institution_sources: list[InstitutionSourceSettings] = []
    request_timeout_seconds: float = 20
    user_agent: str = "IlanDetect/0.1 (+contact@example.com)"
    scheduler_enabled: bool = False
    daily_scan_time: str = "07:30"
    daily_scan_limit: int = 50
    cron_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
