"""`insight` template — lens-aware plain-English gloss of the Senate GESIx
2022 composite for one Planungsraum.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- English only. No jargon. No German words except proper names.
- 'GESIx' itself is not user-facing terminology — the paragraph explains
  the SIGNAL, never the acronym.
- Score is *neighbourhood context*, not a verdict about the flat. The
  paragraph must state that limit explicitly.
- Lens-aware: for Young Family the practical anchors are Kita mix and GP
  waitlists; for Bureaucracy it's Bürgeramt saturation and appointment
  scarcity. Model receives the lens slug so it picks the right lens.
- Ground rules mirror history.py: no invention, no editorialising about
  property values, no 'good/bad neighbourhood' labels.
"""
from __future__ import annotations

import json

SAMPLER = {
    "temp": 0.4,
    "top_p": 0.9,
    "repetition_penalty": 1.15,
    "max_tokens": 320,
}

_SYSTEM = (
    "You interpret a Berlin Senate neighbourhood index (health + social "
    "composite, published 2022) for an English-speaking expat considering "
    "a specific flat. You receive: the Planungsraum name, the citywide "
    "quintile the polygon sits in (1 = top fifth = healthiest / most stable, "
    "5 = bottom fifth), the raw rank out of ~447 Planungsräume, and the "
    "lens the user is browsing (currently only 'young_family'). "
    "Write ONE paragraph, 70–110 words, doing three things in order: "
    "(a) plain-English readout of where the neighbourhood sits in the "
    "citywide distribution — no jargon, do not use the term 'GESIx'; "
    "(b) two concrete daily-life anchors tailored to the lens: for "
    "young_family use childcare cohort mix and local GP wait times as "
    "your concrete anchors; "
    "(c) one honest closing sentence reminding the reader the score is "
    "the polygon around the flat, not the flat itself, and that they "
    "should walk the block before signing. "
    "Ground rules: "
    "1. No invented statistics — you only have quintile + rank; do not "
    "fabricate percentages, absolute numbers, or specific facility names. "
    "2. Do not editorialise about property values or use 'good' / 'bad' "
    "as verdicts about the neighbourhood — the whole point is to inform "
    "a decision, not make it for the user. "
    "3. English only. Do not translate 'Kita', 'Bürgeramt', 'Planungsraum' "
    "— they are proper terminology the user needs to learn. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


_SUPPORTED_LENSES = ("young_family",)


def build_messages(ctx: dict) -> list[dict]:
    slug = (ctx.get("lens") or "young_family").strip()
    if slug not in _SUPPORTED_LENSES:
        # Refuse rather than silently coerce — an older client sending
        # `lens: "bureaucracy"` (removed) or any typo would otherwise get a
        # young-family paragraph rendered under a different tile label. The
        # whole point of the system prompt is to keep the model honest; the
        # dispatcher should be at least as honest.
        raise ValueError(
            f"unsupported lens for gesix_insight: {slug!r} "
            f"(supported: {', '.join(_SUPPORTED_LENSES)})"
        )
    facts = json.dumps({
        "planungsraum":  ctx.get("plr_name") or "unknown",
        "quintile":      ctx.get("quintile_5"),
        "rank_of_total": f"{ctx.get('rang')} of {ctx.get('total') or 447}",
        "lens":          slug,
    }, ensure_ascii=False, indent=2)

    # One-shot to lock the tone and demonstrate refusal of invented stats.
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"planungsraum\": \"Reuterkiez\",\n"
            "  \"quintile\": 5,\n"
            "  \"rank_of_total\": \"402 of 447\",\n"
            "  \"lens\": \"young_family\"\n"
            "}"},
        {"role": "assistant", "content":
            "Your Planungsraum, Reuterkiez, sits in the bottom fifth of Berlin's "
            "neighbourhood health-and-social composite — ranked 402 of 447. For a "
            "family with a small child this most changes two things day to day. "
            "First, your local Kita cohort will skew younger-parent and more "
            "socially-mixed than the citywide average — a feature to some, a "
            "trade-off to others. Second, the nearest GP practices tend to run "
            "fuller waiting lists here, so book new-patient slots well before you "
            "arrive. The score describes the polygon around the flat, not the "
            "flat itself — walk the block at 08:00 on a Tuesday before you sign."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if ctx.get("quintile_5") is None:
        return {"insight": "No neighbourhood profile available for this address "
                            "(outside the Senate's GESIx polygons)."}
    msgs = build_messages(ctx)
    text = backend.generate_from_messages(msgs, **SAMPLER)
    return {"insight": text}


if __name__ == "__main__":
    msgs = build_messages({
        "plr_name": "Test-Kiez", "quintile_5": 2, "rang": 89,
        "total": 447, "lens": "young_family",
    })
    assert msgs[0]["role"] == "system"
    assert "quintile" in msgs[0]["content"].lower()
    assert "Test-Kiez" in msgs[-1]["content"]
    assert "young_family" in msgs[-1]["content"]
    # Explicit rule against invention.
    assert "invented" in msgs[0]["content"].lower() or "fabricate" in msgs[0]["content"].lower()
    # Explicit rule against verdicts.
    assert "verdict" in msgs[0]["content"].lower() or "'good'" in msgs[0]["content"].lower()
    # Empty-input shortcut.
    empty = run(None, {"quintile_5": None})
    assert "outside" in empty["insight"].lower() or "not available" in empty["insight"].lower()

    # Unsupported lens (bureaucracy was removed) must refuse, not silently
    # render a young_family paragraph under the wrong tile label.
    try:
        build_messages({"plr_name": "X", "quintile_5": 2, "rang": 10,
                        "total": 447, "lens": "bureaucracy"})
    except ValueError as e:
        assert "unsupported" in str(e).lower(), str(e)
    else:
        raise AssertionError("expected ValueError on unsupported lens 'bureaucracy'")
    # Empty / default lens still resolves to young_family.
    ok = build_messages({"plr_name": "X", "quintile_5": 2, "rang": 10,
                         "total": 447})
    assert "young_family" in ok[-1]["content"], ok[-1]["content"]
    print("insight.py selfcheck OK")
