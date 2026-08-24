from __future__ import annotations

# Email HTML is intentionally kept inline for broad client compatibility.
# ruff: noqa: E501
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
        listing for listing in matching if listing.id in updated_ids and listing.id not in used_ids
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


def render_digest(
    content: DigestContent, *, today: date, unsubscribe_url: str | None = None
) -> tuple[str, str]:
    count = len(content.listing_ids)
    subject = f"{today:%d.%m.%Y} - Kamu İlanları"
    sections = [
        _render_section("Size uygun yeni ilanlar", content.new, today),
        _render_section("Güncellenen ilanlar", content.updated, today),
        _render_section("Başvurusu üç gün içinde bitecek ilanlar", content.expiring, today),
    ]
    if count == 0:
        sections = [
            '<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;'
            'padding:28px;text-align:center;color:#475569">'
            '<div style="font-size:34px;line-height:1;margin-bottom:12px">✓</div>'
            '<div style="font-size:16px;font-weight:700;color:#0f172a">Bugün yeni eşleşme yok</div>'
            '<div style="font-size:14px;line-height:22px;margin-top:6px">'
            "Kriterlerinize uygun yeni bir ilan yayımlandığında burada göreceksiniz.</div></div>"
        ]
    unsubscribe = ""
    if unsubscribe_url:
        safe_unsubscribe_url = escape(unsubscribe_url, quote=True)
        unsubscribe = (
            f'<br><a href="{safe_unsubscribe_url}" style="color:#64748b;'
            'text-decoration:underline">Abonelikten çık</a>'
        )
    html = f"""<!doctype html>
<html lang="tr">
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#0f172a">
  <div style="display:none;max-height:0;overflow:hidden;color:transparent">
    Bugünkü kamu ilanı özetinizde {count} eşleşme var.
  </div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f1f5f9">
    <tr><td align="center" style="padding:28px 12px">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:720px">
        <tr><td style="background:#172554;background:linear-gradient(135deg,#172554,#2563eb);border-radius:18px 18px 0 0;padding:30px 32px;color:#ffffff">
          <div style="font-size:12px;letter-spacing:1.4px;text-transform:uppercase;font-weight:700;color:#bfdbfe">ILANDETECT</div>
          <div style="font-size:28px;line-height:36px;font-weight:800;margin-top:8px">Günlük kamu ilanları</div>
          <div style="font-size:14px;line-height:22px;color:#dbeafe;margin-top:6px">{today:%d.%m.%Y} tarihli kişisel özetiniz</div>
        </td></tr>
        <tr><td style="background:#ffffff;padding:20px 24px;border-bottom:1px solid #e2e8f0">
          {_render_stats(content)}
        </td></tr>
        <tr><td style="background:#f8fafc;padding:8px 24px 28px">
          {"".join(sections)}
        </td></tr>
        <tr><td style="padding:22px 24px;text-align:center;color:#64748b;font-size:12px;line-height:19px">
          Başvuru yapmadan önce şartları ve tarihleri resmî ilan sayfasından kontrol edin.<br>
          Bu e-posta IlanDetect tarafından otomatik olarak hazırlanmıştır.
          {unsubscribe}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return subject, html


async def send_daily_digest(session: Session, settings: Settings) -> dict:
    filters = session.scalar(select(UserFilter).limit(1))
    if filters is None:
        return {"status": "skipped", "reason": "user_filter_missing"}
    if not filters.subscribed:
        return {"status": "skipped", "reason": "unsubscribed"}
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

    subject, html = render_digest(
        content,
        today=today,
        unsubscribe_url=f"{settings.public_base_url.rstrip('/')}/unsubscribe",
    )
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
    return (
        '<div style="font-size:17px;font-weight:800;color:#0f172a;'
        f'margin:24px 2px 12px">{escape(title)} '
        f'<span style="color:#64748b;font-size:13px;font-weight:600">({len(listings)})</span></div>'
        f"{cards}"
    )


def _render_listing(listing: Listing, today: date) -> str:
    deadline = "Son başvuru bilgisi yok"
    if listing.application_end:
        days = (listing.application_end - today).days
        deadline = f"Son başvuru: {listing.application_end:%d.%m.%Y} ({days} gün kaldı)"
    metadata = [
        ("Şehir", ", ".join(listing.cities) or "Tüm Türkiye / belirtilmedi"),
        ("Kontenjan", str(listing.quota) if listing.quota else "Belirtilmedi"),
        ("Son başvuru", deadline.removeprefix("Son başvuru: ")),
    ]
    if listing.kpss_required is not None:
        kpss = "Gerekli" if listing.kpss_required else "Gerekli değil"
        if listing.kpss_types:
            kpss += f" ({', '.join(listing.kpss_types)})"
        metadata.append(("KPSS", kpss))
    url = escape(listing.application_url or listing.official_url, quote=True)
    category = escape(listing.category or "Kamu personeli")
    metadata_html = "".join(
        '<td width="50%" valign="top" style="padding:7px 8px 7px 0">'
        f'<div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.4px">{escape(label)}</div>'
        f'<div style="font-size:13px;line-height:19px;color:#334155;margin-top:2px">{escape(value)}</div></td>'
        for label, value in metadata
    )
    return (
        '<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;'
        'padding:20px;margin:12px 0;box-shadow:0 1px 2px rgba(15,23,42,.04)">'
        f'<span style="display:inline-block;background:#eff6ff;color:#1d4ed8;border-radius:999px;'
        f'padding:5px 9px;font-size:11px;font-weight:700">{category}</span>'
        f'<div style="font-size:12px;line-height:18px;font-weight:700;color:#64748b;margin-top:13px">'
        f"{escape(listing.institution or 'Kurum belirtilmedi')}</div>"
        f'<div style="font-size:18px;line-height:25px;font-weight:800;color:#0f172a;margin-top:4px">'
        f"{escape(listing.position)}</div>"
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin-top:12px"><tr style="display:flex;flex-wrap:wrap">{metadata_html}</tr></table>'
        f'<a href="{url}" style="display:block;background:#2563eb;color:#ffffff;text-decoration:none;'
        "text-align:center;border-radius:9px;padding:12px 16px;margin-top:14px;font-size:14px;"
        'font-weight:700">Resmî ilanı görüntüle&nbsp; →</a>'
        "</div>"
    )


def _render_stats(content: DigestContent) -> str:
    stats = (
        ("Yeni ilan", len(content.new), "#2563eb", "#eff6ff"),
        ("Güncellenen", len(content.updated), "#7c3aed", "#f5f3ff"),
        ("Yakında biten", len(content.expiring), "#dc2626", "#fef2f2"),
    )
    cells = "".join(
        f'<td width="33.33%" align="center" style="padding:5px">'
        f'<div style="background:{background};border-radius:11px;padding:13px 5px">'
        f'<div style="font-size:22px;font-weight:800;color:{color}">{value}</div>'
        f'<div style="font-size:11px;color:#64748b;margin-top:3px">{label}</div></div></td>'
        for label, value, color, background in stats
    )
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>{cells}</tr></table>'
