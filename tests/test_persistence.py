from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import ListingChange
from app.persistence import get_or_create_source, upsert_listing
from app.schemas import NormalizedListing


def make_listing(position: str = "Mühendis") -> NormalizedListing:
    return NormalizedListing(
        source_key="kariyer_kapisi",
        external_id="abc",
        position=position,
        official_url="https://kariyerkapisi.gov.tr/IlanDetay?i=abc",
    )


def test_upsert_creates_then_ignores_same_listing() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = get_or_create_source(
            session,
            key="kariyer_kapisi",
            name="Kariyer Kapısı",
            base_url="https://kariyerkapisi.gov.tr/isealim",
        )
        first = upsert_listing(session, source, make_listing())
        second = upsert_listing(session, source, make_listing())
        session.commit()
        first_id = first.listing.id
        second_id = second.listing.id

    assert first.state == "new"
    assert second.state == "unchanged"
    assert first_id == second_id


def test_upsert_records_changed_fields() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = get_or_create_source(
            session,
            key="kariyer_kapisi",
            name="Kariyer Kapısı",
            base_url="https://kariyerkapisi.gov.tr/isealim",
        )
        upsert_listing(session, source, make_listing())
        changed = upsert_listing(session, source, make_listing("Uzman"))
        session.commit()
        history = session.scalars(select(ListingChange)).all()

    assert changed.state == "updated"
    assert changed.changed_fields == ["position"]
    assert len(history) == 1
