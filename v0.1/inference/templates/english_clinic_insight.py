"""`english_clinic_insight` — plain-English gloss of the 'English-speaking clinic' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- OSM data is community-tagged — inner-district coverage is good but
  outer districts may under-report. The caveat is mandatory in the output.
- The paragraph must surface that TK/AOK helplines and Doctolib offer
  English-language access as backup options.
- No invented statistics or clinic names beyond the payload.
- No editorialising about the neighbourhood.
- English only except 'Hausarzt' / 'Kassenarzt' proper terms.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret the English-speaking clinic proximity signal for a newcomer "
    "expat in Berlin. You receive: the tier (green / amber / red), the rule text, "
    "the numeric readout (distance to nearest English-tagged practice), and a "
    "shortlist of the closest options each with name and distance in metres. "
    "Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of how close the nearest English-speaking medical "
    "practice is and what that means for an urgent appointment; "
    "(b) important data caveat: this signal comes from OSM community-tagging — "
    "coverage is good in inner districts but outer districts may under-report "
    "English-language practices, so the map is not exhaustive; "
    "(c) practical backup options for every newcomer regardless of tier: "
    "TK and AOK statutory health insurers both run English-language helplines, "
    "and Doctolib (the booking platform) lets you filter by language preference. "
    "Ground rules: "
    "1. No invented statistics or clinic names beyond the payload. "
    "2. No verdicts about the neighbourhood. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"red\",\n"
    "  \"rule\": \"no English-tagged practice nearby — expect German or telemedicine\",\n"
    "  \"numeric\": \"\",\n"
    "  \"top\": []\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "No English-tagged medical practices appear nearby in the OSM dataset — "
    "keep in mind this data relies on community tagging and outer districts "
    "often under-report, so there may be more options than the map shows. "
    "In the meantime, TK and AOK both run English-language helplines for "
    "health queries, and Doctolib (the appointment platform) lets you filter "
    "doctors by language preference. For urgent care, the Kassenärztliche "
    "Vereinigung Berlin hotline (030 31003) connects you to an on-duty "
    "doctor around the clock."
)

_EMPTY_MSG = (
    "No English-tagged practices found nearby (OSM community data — outer "
    "districts may under-report). TK and AOK both offer English-language "
    "helplines; Doctolib lets you filter by language. For urgent care, "
    "the KV Berlin hotline (030 31003) connects you to an on-duty doctor."
)


def build_messages(ctx: dict) -> list[dict]:
    from inference.templates._insight_base import build_tier_messages
    return build_tier_messages(
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        ctx=ctx,
    )


def run(backend, ctx: dict) -> dict:
    return run_tier(
        backend, ctx,
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        empty_msg=_EMPTY_MSG,
    )


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "red",
        "rule": "no English-tagged practice nearby — expect German or telemedicine",
        "numeric": "",
        "features": [],
    })
    assert msgs[0]["role"] == "system"
    # System prompt mentions inversion rule
    assert "invert" in msgs[0]["content"].lower() or "never invert" in msgs[0]["content"].lower()
    # System prompt mentions OSM caveat
    assert "osm" in msgs[0]["content"].lower() or "community-tag" in msgs[0]["content"].lower()
    # System prompt mentions TK/AOK and Doctolib
    assert "doctolib" in msgs[0]["content"].lower(), "system must mention Doctolib"
    assert "tk" in msgs[0]["content"].lower() or "aok" in msgs[0]["content"].lower(), \
        "system must mention TK or AOK helplines"
    # Red exemplar must acknowledge the difficulty
    exemplar_lower = msgs[2]["content"].lower()
    assert "no" in exemplar_lower or "under-report" in exemplar_lower, \
        "red exemplar must acknowledge the gap"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    # Final user message
    assert msgs[-1]["role"] == "user"
    print("english_clinic_insight.py selfcheck OK")
