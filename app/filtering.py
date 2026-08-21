from __future__ import annotations

from datetime import date

from app.models import Listing, UserFilter


def listing_matches(listing: Listing, filters: UserFilter, *, today: date | None = None) -> bool:
    today = today or date.today()
    searchable = _normalize(
        " ".join(
            filter(None, [listing.institution, listing.position, *listing.positions, listing.text])
        )
    )
    if filters.cities and not _intersects(filters.cities, listing.cities):
        return False
    if filters.include_keywords and not any(
        _normalize(keyword) in searchable for keyword in filters.include_keywords
    ):
        return False
    if filters.exclude_keywords and any(
        _normalize(keyword) in searchable for keyword in filters.exclude_keywords
    ):
        return False
    if filters.education_levels and not _intersects(filters.education_levels, listing.education):
        return False
    if filters.kpss_required is not None and listing.kpss_required != filters.kpss_required:
        return False
    if filters.kpss_types and not _intersects(filters.kpss_types, listing.kpss_types):
        return False
    if filters.institutions and not any(
        _normalize(value) in _normalize(listing.institution or "")
        for value in filters.institutions
    ):
        return False
    if filters.deadline_days is not None:
        if listing.application_end is None:
            return False
        remaining = (listing.application_end - today).days
        if remaining < 0 or remaining > filters.deadline_days:
            return False
    return True


def _intersects(expected: list[str], actual: list[str]) -> bool:
    normalized_actual = {_normalize(value) for value in actual}
    return any(_normalize(value) in normalized_actual for value in expected)


def _normalize(value: str) -> str:
    return " ".join(value.replace("İ", "i").replace("I", "ı").casefold().split())
