from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings
from app.db import SessionLocal
from app.digest import send_daily_digest
from app.scanner import scan_kariyer_kapisi

logger = logging.getLogger(__name__)


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    hour, minute = _parse_time(settings.daily_scan_time)
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        scheduled_scan,
        CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
        kwargs={"settings": settings},
        id="daily-kariyer-kapisi-scan",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler


async def scheduled_scan(settings: Settings) -> None:
    with SessionLocal() as session:
        try:
            await scan_kariyer_kapisi(session, settings, limit=settings.daily_scan_limit)
            await send_daily_digest(session, settings)
        except Exception:
            logger.exception("Scheduled Kariyer Kapısı scan failed")


def _parse_time(value: str) -> tuple[int, int]:
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("DAILY_SCAN_TIME HH:MM biçiminde olmalı") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("DAILY_SCAN_TIME geçerli bir saat olmalı")
    return hour, minute
