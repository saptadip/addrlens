"""Unit tests for `app.core.addr.parse_address`.

Ground truth: the selfcheck block at the bottom of `app/core/addr.py`.
"""
import pytest

from app.core.addr import parse_address


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Happy path — comma-separated PLZ.
        ("Kastanienallee 12, 10435", ("Kastanienallee", "12", "10435")),
        # No comma — space-separated PLZ.
        ("Kastanienallee 12 10435", ("Kastanienallee", "12", "10435")),
        # Trailing "Berlin" after PLZ.
        ("Kastanienallee 12, 10435 Berlin", ("Kastanienallee", "12", "10435")),
        # Borough injected between street and PLZ (expat-common).
        ("Sybelstrasse 59, Charlottenburg, 10629 Berlin",
         ("Sybelstrasse", "59", "10629")),
        # Borough injected, no trailing Berlin.
        ("Sybelstrasse 59, Charlottenburg, 10629",
         ("Sybelstrasse", "59", "10629")),
        # Trailing "Berlin" with no commas at all.
        ("Kastanienallee 12 10435 Berlin",
         ("Kastanienallee", "12", "10435")),
    ],
)
def test_parse_address_happy_paths(raw, expected):
    assert parse_address(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "Nostreet"])
def test_parse_address_rejects_invalid_input(raw):
    assert parse_address(raw) is None


def test_parse_address_multi_word_street():
    # Multi-word street name preserved verbatim.
    assert parse_address("Karl-Marx-Allee 100, 10243") == (
        "Karl-Marx-Allee", "100", "10243",
    )


def test_parse_address_hnr_with_letter_suffix():
    # Letter suffix on hnr comes through — Berlin BOD splits it downstream
    # but the parser must not swallow the trailing character.
    result = parse_address("Bergmannstraße 44A, 10961")
    assert result is not None
    street, hnr, plz = result
    assert street == "Bergmannstraße"
    assert hnr == "44A"
    assert plz == "10961"
