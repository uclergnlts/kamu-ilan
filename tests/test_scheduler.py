import pytest

from app.scheduler import _parse_time


def test_parse_daily_scan_time() -> None:
    assert _parse_time("07:30") == (7, 30)


@pytest.mark.parametrize("value", ["24:00", "12:60", "wrong"])
def test_reject_invalid_daily_scan_time(value: str) -> None:
    with pytest.raises(ValueError):
        _parse_time(value)
