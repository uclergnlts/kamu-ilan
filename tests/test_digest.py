from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.digest import prepare_digest, render_digest
from app.models import EmailDelivery, Listing, Source, UserFilter


def setup_digest_data() -> tuple[Session, UserFilter, Listing]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    source = Source(key="test", name="Test", base_url="https://example.gov.tr")
    filters = UserFilter(
        email="user@example.com",
        cities=["ANKARA"],
        include_keywords=[],
        exclude_keywords=[],
        education_levels=[],
        kpss_required=None,
        kpss_types=[],
        institutions=[],
        deadline_days=None,
    )
    listing = Listing(
        source_id=1,
        external_id="abc",
        institution="Örnek & Kurum",
        position="Mühendis <Alımı>",
        positions=["MÜHENDİS"],
        category="Personel",
        cities=["ANKARA"],
        quota=2,
        education=["Lisans"],
        kpss_required=True,
        kpss_types=["P3"],
        application_end=date(2026, 8, 22),
        official_url="https://example.gov.tr/ilan/abc",
        fingerprint="x" * 64,
    )
    session.add_all([source, filters, listing])
    session.commit()
    return session, filters, listing


def test_new_listing_is_not_duplicated_in_expiring_section() -> None:
    session, filters, listing = setup_digest_data()
    content = prepare_digest(session, filters, today=date(2026, 8, 20))

    assert [item.id for item in content.new] == [listing.id]
    assert content.updated == []
    assert content.expiring == []
    session.close()


def test_sent_listing_can_appear_as_expiring_reminder() -> None:
    session, filters, listing = setup_digest_data()
    session.add(
        EmailDelivery(
            user_filter_id=filters.id,
            sent_at=datetime(2026, 8, 19, 8),
            status="sent",
            listing_ids=[listing.id],
        )
    )
    session.commit()

    content = prepare_digest(session, filters, today=date(2026, 8, 20))

    assert content.new == []
    assert [item.id for item in content.expiring] == [listing.id]
    session.close()


def test_digest_html_escapes_listing_content() -> None:
    session, filters, _ = setup_digest_data()
    content = prepare_digest(session, filters, today=date(2026, 8, 20))
    subject, html = render_digest(
        content,
        today=date(2026, 8, 20),
        unsubscribe_url="https://example.com/unsubscribe",
    )

    assert subject == "20.08.2026 - Kamu İlanları"
    assert "Örnek &amp; Kurum" in html
    assert "Mühendis &lt;Alımı&gt;" in html
    assert "Günlük kamu ilanları" in html
    assert "Resmî ilanı görüntüle" in html
    assert "Yeni ilan" in html
    assert 'href="https://example.com/unsubscribe"' in html
    assert "Abonelikten çık" in html
    session.close()
