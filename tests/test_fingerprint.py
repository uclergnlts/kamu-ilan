from app.schemas import NormalizedListing
from app.services import listing_fingerprint


def test_fingerprint_is_stable_and_changes_with_content() -> None:
    listing = NormalizedListing(
        source_key="ilan_gov_tr",
        external_id="123",
        position="Mühendis",
        official_url="https://www.ilan.gov.tr/ilan/123",
    )
    same_content_other_source_id = listing.model_copy(update={"external_id": "456"})
    changed = listing.model_copy(update={"position": "Uzman"})

    assert listing_fingerprint(listing) == listing_fingerprint(same_content_other_source_id)
    assert listing_fingerprint(listing) != listing_fingerprint(changed)

