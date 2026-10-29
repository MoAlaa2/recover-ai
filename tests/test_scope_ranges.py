"""Budget chips and measurements must never be declined as maths (A1)."""
import pytest

from app.services.catalog import is_in_scope


@pytest.mark.parametrize("text", [
    "Under 80 SAR", "80-150 SAR", "80–150 SAR", "over 150 SAR", "No limit",
    "١٠٠-٢٥٠ ر.س", "80-150 ر.س", "أقل من ٨٠ ريال", "3×2.5", "2.5*3",
    "3 x 2.5 m", "the window is 3m wide", "200 cm", "٣×٢.٥ م",
])
def test_ranges_and_sizes_stay_in_scope(text):
    assert is_in_scope(text)


@pytest.mark.parametrize("text", ["what is 12*7", "solve for x", "2+2"])
def test_real_maths_still_declined(text):
    assert not is_in_scope(text)
