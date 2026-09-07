"""Unit tests for `app.core.gloss.gloss` — bilingual glossary injection.

Ground truth: the selfcheck at the bottom of `app/core/gloss.py`. The
glossary lives on the CityConfig (per plan §7.3), so we import Berlin's.
"""
import pytest

from app.core.gloss import gloss


@pytest.fixture(scope="module")
def berlin_glossary(berlin_config):
    # Reuse the session-scoped fixture from tests/conftest.py.
    return berlin_config.bilingual_glossary


def test_gloss_injects_english_for_freier_traeger(berlin_glossary):
    out = gloss("run by a freier Träger", berlin_glossary)
    assert "(a non-profit or private provider)" in out


def test_gloss_injects_english_for_situationsansatz(berlin_glossary):
    out = gloss("using the Situationsansatz approach", berlin_glossary)
    assert "(a child-led Berlin pedagogy)" in out


def test_gloss_catches_common_situationssatz_misspelling(berlin_glossary):
    # Small models frequently type this variant; the glossary catches it.
    out = gloss("uses the Situationssatz approach", berlin_glossary)
    assert "(a child-led Berlin pedagogy)" in out


def test_gloss_injects_english_for_kitas(berlin_glossary):
    out = gloss("26 Kitas within a walk", berlin_glossary)
    assert "26 Kitas (daycare) within" in out


def test_gloss_does_not_double_gloss(berlin_glossary):
    # Model already glossed — parenthetical follows within ~60 chars → skip.
    original = "freier Träger (already glossed)"
    assert gloss(original, berlin_glossary) == original


def test_gloss_empty_glossary_is_noop(berlin_glossary):
    # Independent of the Berlin glossary — a caller passing [] must get
    # its input back verbatim.
    assert gloss("Träger something", []) == "Träger something"


@pytest.mark.parametrize(
    "text",
    ["", "no german terms here", "plain english about schools"],
)
def test_gloss_leaves_non_matching_text_unchanged(text, berlin_glossary):
    assert gloss(text, berlin_glossary) == text
