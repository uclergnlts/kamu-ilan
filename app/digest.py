from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.filtering import listing_matches
from app.models import EmailDelivery, Listing, ListingChange, UserFilter, utcnow


@dataclass(frozen=True)
class DigestContent:
    new: list[Listing]
    updated: list[Listing]
    expiring: list[Listing]

    @property
    def listing_ids(self) -> list[int]:
        return [item.id for group in (self.new, self.updated, self.expiring) for item in group]


def prepare_digest(session: Session, filters: UserFilter, *, today: date) -> DigestContent:
    matching = [
        listing
        for listing in session.scalars(select(Listing).order_by(Listing.published_at.desc())).all()
        if listing_matches(listing, filters, today=today)
    ]
    deliveries = session.scalars(
        select(EmailDelivery)
        .where(
            EmailDelivery.user_filter_id == filters.id,
            EmailDelivery.status == "sent",
        )
        .order_by(EmailDelivery.sent_at.desc())
    ).all()
    sent_ids = {listing_id for delivery in deliveries for listing_id in delivery.listing_ids}
    last_sent_at = deliveries[0].sent_at if deliveries else None
    updated_ids = set()
    if last_sent_at:
        updated_ids = set(
            session.scalars(
                select(ListingChange.listing_id).where(ListingChange.detected_at > last_sent_at)
            ).all()
        )

    new = [listing for listing in matching if listing.id not in sent_ids]
    used_ids = {listing.id for listing in new}
    updated = [
        listing
        for listing in matching
        if listing.id in updated_ids and listing.id not in used_ids
    ]
    used_ids.update(listing.id for listing in updated)
    expiring = [
        listing
        for listing in matching
        if listing.id not in used_ids
        and listing.application_end is not None
        and 0 <= (listing.application_end - today).days <= 3
    ]
    return DigestContent(new=new, updated=updated, expiring=expiring)


def render_digest(content: DigestContent, *, today: date) -> tuple[str, str]:
    count = len(content.listing_ids)
    subject = f"Kamu ilanları günlük özeti — {count} eşleşme"
    sections = [
        _render_section("Size uygun yeni ilanlar", content.new, today),
        _render_section("Güncellenen ilanlar", content.updated, today),
        _render_section("Başvurusu üç gün içinde bitecek ilanlar", content.expiring, today),
    ]
    if count == 0:
        sections = ["<p>Bugün kriterlerinize uygun yeni ilan bulunamadı.</p>"]
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:720px;margin:auto;color:#172033">'
        '<h1 style="font-size:22px">IlanDetect günlük özeti</h1>'
        + "".join(sections)
        + '<p style="font-size:12px;color:#687386">'
        + "Başvurmadan önce resmî ilan metnini kontrol edin.</p>"
        + "</div>"
    )
    return subject, html


async def send_daily_digest(session: Session, settings: Settings) -> dict:
    filters = session.scalar(select(UserFilter).limit(1))
    if filters is None:
        return {"status": "skipped", "reason": "user_filter_missing"}
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    content = prepare_digest(session, filters, today=today)
    if not content.listing_ids and not filters.send_empty_digest:
        return {"status": "skipped", "reason": "no_matches"}
    if not settings.resend_api_key:
        return {"status": "preview", "reason": "resend_api_key_missing"}

    existing = session.scalar(
        select(EmailDelivery).where(
            EmailDelivery.user_filter_id == filters.id,
            EmailDelivery.status == "sent",
            EmailDelivery.sent_at >= datetime.combine(today, datetime.min.time()),
        )
    )
    if existing:
        return {"status": "already_sent", "delivery_id": existing.id}

    subject, html = render_digest(content, today=today)
    delivery = EmailDelivery(
        user_filter_id=filters.id,
        status="pending",
        listing_ids=content.listing_ids,
    )
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Idempotency-Key": f"daily-digest/{filters.id}/{today.isoformat()}",
                },
                json={
                    "from": settings.email_from,
                    "to": [filters.email],
                    "subject": subject,
                    "html": html,
                    "tags": [{"name": "type", "value": "daily-digest"}],
                },
            )
            response.raise_for_status()
            delivery.provider_id = response.json()["id"]
            delivery.status = "sent"
            delivery.sent_at = utcnow()
            session.commit()
            return {
                "status": "sent",
                "delivery_id": delivery.id,
                "provider_id": delivery.provider_id,
            }
    except Exception as exc:
        delivery.status = "failed"
        delivery.error = str(exc)[:2000]
        session.commit()
        raise


def _render_section(title: str, listings: list[Listing], today: date) -> str:
    if not listings:
        return ""
    cards = "".join(_render_listing(listing, today) for listing in listings)
    return f'<h2 style="font-size:18px;margin-top:28px">{escape(title)}</h2>{cards}'


def _render_listing(listing: Listing, today: date) -> str:
    deadline = "Son başvuru bilgisi yok"
    if listing.application_end:
        days = (listing.application_end - today).days
        deadline = f"Son başvuru: {listing.application_end:%d.%m.%Y} ({days} gün kaldı)"
    details = " · ".join(
        part
        for part in [
            ", ".join(listing.cities),
            f"{listing.quota} kontenjan" if listing.quota else "",
            deadline,
        ]
        if part
    )
    url = escape(listing.application_url or listing.official_url, quote=True)
    return (
        '<div style="border:1px solid #dde3ec;border-radius:10px;padding:16px;margin:10px 0">'
        f'<div style="font-weight:bold">{escape(listing.institution or "Kurum belirtilmedi")}</div>'
        f'<div style="margin:6px 0">{escape(listing.position)}</div>'
        f'<div style="font-size:13px;color:#566176">{escape(details)}</div>'
        f'<a href="{url}" style="display:inline-block;margin-top:10px">Resmî ilana git</a>'
        "</div>"
    )
