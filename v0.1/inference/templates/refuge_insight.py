"""`refuge_insight` template — plain-English gloss of the Young Family
'Quiet / green refuge nearby' tile for one address.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Same template naming convention as gesix_insight — every card that
  earns an AI paragraph gets its own `<card_key>_insight` template so
  the system prompt can be tuned to that card's specific facts.
- Refuge tile combines TWO signals: nearest Berlin 'Ruhige Gebiete'
  quiet zone AND street-tree canopy coverage in a bbox around the flat.
  The paragraph should acknowledge both, not just one.
- No German words except proper names (park names, Bezirk).
- No editorialising about 'good/bad neighbourhood'.
- No invention — the model only says what the payload contains.
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
    "You interpret Berlin's 'quiet & green refuge' signal for an "
    "English-speaking expat considering a specific flat. You receive: "
    "the nearest official 'Ruhige Gebiete' quiet-zone (name, distance in "
    "metres, optional size in hectares), plus a street-tree canopy summary "
    "for a bbox around the flat (count of street trees, crown-coverage "
    "percent, average tree age, top 3 species by count). Write ONE "
    "paragraph, 70–110 words, doing three things in order: "
    "(a) plain-English readout of the quiet-zone distance — if it's within "
    "800 metres call it walkable, 800–1500 m a bike ride, further a "
    "commitment; if the payload omits the quiet zone say so plainly; "
    "(b) plain-English readout of the street-tree canopy. Berlin's "
    "Baumbestand tracks REGISTERED STREET TREES ONLY (not park or "
    "private-garden trees), and the metric divides crown-disk area by "
    "the whole search-disk area — most of that disk is buildings, so "
    "real Berlin residential streets rarely exceed the low teens. "
    "Frame the number on that scale: under 5% is sparse, 5–10% "
    "moderate, above 10% clearly tree-dense for a Straßenbäume-only "
    "signal. Mention the top species when present; "
    "(c) one honest closing sentence linking the two signals to a young "
    "family's daily life — where the child will actually play and walk. "
    "Ground rules: "
    "1. No invented statistics beyond the payload. No fabricated park names. "
    "2. No 'good' or 'bad' as verdicts about the neighbourhood — describe, "
    "don't judge. "
    "3. English only. Do not translate 'Ruhige Gebiete', 'Kiez', 'Bezirk' — "
    "they're proper terminology the user needs to learn. "
    "4. If a signal is missing entirely (no quiet zone AND zero trees), "
    "say so plainly in one sentence instead of writing 90 words of filler. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    quiet = ctx.get("quiet") or {}
    trees = ctx.get("trees") or {}
    facts = json.dumps({
        "planungsraum_hint": ctx.get("plr_hint") or None,
        "quiet_zone": {
            "name":         quiet.get("name"),
            "distance_m":   quiet.get("distance_m"),
            "size_ha":      quiet.get("size_ha"),
        } if quiet else None,
        "street_trees": {
            "count":              trees.get("count"),
            "crown_coverage_pct": trees.get("crown_coverage_pct"),
            "avg_age_yr":         trees.get("avg_age_yr"),
            "tallest_m":          trees.get("tallest_m"),
            "top_species":        (trees.get("top_species") or [])[:3],
        } if trees else None,
        "tier":               ctx.get("tier"),
    }, ensure_ascii=False, indent=2)

    # One-shot demonstrating both-signals handling + honest gap language.
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"quiet_zone\": {\"name\": \"Volkspark Friedrichshain\", "
            "\"distance_m\": 620, \"size_ha\": 49},\n"
            "  \"street_trees\": {\"count\": 199, "
            "\"crown_coverage_pct\": 11.4, \"avg_age_yr\": 41, "
            "\"top_species\": [{\"name\":\"Gemeine Rosskastanie\",\"count\":38}, "
            "{\"name\":\"Winter-Linde\",\"count\":29}, "
            "{\"name\":\"Kaiserlinde\",\"count\":22}]},\n"
            "  \"tier\": \"green\"\n"
            "}"},
        {"role": "assistant", "content":
            "The nearest official quiet zone, Volkspark Friedrichshain, sits "
            "620 metres from your door — a comfortable stroller walk. The park "
            "itself is 49 hectares, big enough for a full afternoon. Closer in, "
            "the block around the flat carries roughly 11% street-tree "
            "canopy — clearly tree-dense for a Straßenbäume-only signal, with "
            "Gemeine Rosskastanie (horse-chestnut) and Winter-Linde (linden) "
            "leading the local mix. For a young family this means daily walks "
            "stay green even before you reach the park, and the summer heat "
            "won't hit the pavement at full strength."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    quiet = ctx.get("quiet") or {}
    trees = ctx.get("trees") or {}
    if not quiet.get("name") and not trees.get("count"):
        return {"insight":
                "No 'Ruhige Gebiete' quiet zone within reach and no street-tree "
                "data recorded for this block. This is a hard signal that the "
                "block is neither quiet-designated nor densely tree-lined — "
                "walk it in person before you sign."}
    msgs = build_messages(ctx)
    text = backend.generate_from_messages(msgs, **SAMPLER)
    return {"insight": text}


if __name__ == "__main__":
    msgs = build_messages({
        "quiet": {"name": "Test-Park", "distance_m": 500, "size_ha": 20},
        "trees": {"count": 150, "crown_coverage_pct": 6.4, "avg_age_yr": 35,
                  "top_species": [{"name": "Linde", "count": 40}]},
        "tier":  "green",
    })
    assert msgs[0]["role"] == "system"
    sys_low = msgs[0]["content"].lower()
    assert "quiet zone" in sys_low
    assert "crown-coverage" in sys_low or "canopy" in sys_low
    assert "Test-Park" in msgs[-1]["content"]
    # No invention rule.
    assert "invent" in sys_low or "fabricat" in sys_low
    # Anti-regression on the canopy calibration — same contract as the
    # street_trees_insight retune. The system prompt must anchor the
    # Straßenbäume-only 5 / 10 % scale AND drop the stale 15 / 20 / 25 %
    # anchors that would make a 22 % canopy read "genuinely shady" when
    # it is physically unreachable.
    #
    # Notation is `%` glyph (matches street_trees_insight sibling — one
    # canonical form for the numeric calibration statement across both
    # canopy templates so a future edit can't reintroduce a "percent"
    # spelling that would look like drift.
    assert "straßenbäume" in sys_low or "strassenbaume" in sys_low or \
           "street tree" in sys_low, \
        "system must name the Straßenbäume-only limitation"
    assert "5%" in sys_low and "10%" in sys_low, \
        "system must anchor the retuned 5 / 10 % scale (as `%` glyph)"
    assert "5 percent" not in sys_low and "10 percent" not in sys_low, \
        "system must use `%` glyph, not spelled-out 'percent' (parity with street_trees_insight)"
    assert "20%" not in sys_low and "22%" not in sys_low and "25%" not in sys_low, \
        "system must not carry the stale 20 / 22 / 25 % 'shady' anchors"
    # Green exemplar canopy value must be within the plausible
    # Straßenbäume-only range (single digits to low teens).
    ex_assistant = msgs[2]["content"]
    assert "22%" not in ex_assistant and "22.4" not in ex_assistant and \
           "22 percent" not in ex_assistant, \
        "green exemplar must not carry the stale 22 % canopy anchor"
    assert "11%" in ex_assistant, \
        "green exemplar must show the retuned 11 % canopy value (as `%` glyph)"
    # Empty-both shortcut.
    empty = run(None, {"quiet": {}, "trees": {}})
    assert "walk it in person" in empty["insight"] or "hard signal" in empty["insight"].lower()
    print("refuge_insight.py selfcheck OK")
