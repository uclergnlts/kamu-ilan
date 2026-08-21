from datetime import date

from app.filtering import listing_matches
from app.models import Listing, UserFilter


def listing() -> Listing:
    return Listing(
        source_id=1,
        external_id="abc",
        institution="MİLLİ EĞİTİM BAKANLIĞI",
        position="Bilişim Personeli",
        positions=["MÜHENDİS"],
        category="Sözleşmeli Personel",
        cities=["ANKARA"],
        quota=3,
        education=["Lisans"],
        kpss_required=True,
        kpss_types=["P3"],
        application_start=date(2026, 8, 10),
        application_end=date(2026, 8, 23),
        text="Yazılım geliştirme alanında mühendis alınacaktır.",
        official_url="https://example.gov.tr/ilan/abc",
        fingerprint="x" * 64,
    )


def filters(**updates) -> UserFilter:
    values = {
        "email": "user@example.com",
        "cities": [],
        "include_keywords": [],
        "exclude_keywords": [],
        "education_levels": [],
        "kpss_required": None,
        "kpss_types": [],
        "institutions": [],
        "deadline_days": None,
    }
    values.update(updates)
    return UserFilter(**values)


def test_listing_matches_combined_filters() -> None:
    assert listing_matches(
        listing(),
        filters(
            cities=["Ankara"],
            include_keywords=["yazılım"],
            education_levels=["lisans"],
            kpss_required=True,
            kpss_types=["p3"],
            institutions=["milli eğitim"],
            deadline_days=3,
        ),
        today=date(2026, 8, 20),
    )


def test_excluded_keyword_rejects_listing() -> None:
    assert not listing_matches(
        listing(), filters(exclude_keywords=["mühendis"]), today=date(2026, 8, 20)
    )


def test_unknown_deadline_does_not_match_deadline_filter() -> None:
    item = listing()
    item.application_end = None
    assert not listing_matches(item, filters(deadline_days=3), today=date(2026, 8, 20))
