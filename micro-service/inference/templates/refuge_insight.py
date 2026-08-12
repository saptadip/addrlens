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
    "(b) plain-English readout of the street-tree canopy — crown-coverage "
    "under 10 percent is sparse, 10–20 percent moderate, above 20 percent "
    "genuinely shady; mention the top species when present; "
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
            "  \"street_trees\": {\"count\": 187, "
            "\"crown_coverage_pct\": 22.4, \"avg_age_yr\": 41, "
            "\"top_species\": [{\"name\":\"Gemeine Rosskastanie\",\"count\":38}, "
            "{\"name\":\"Kaiserlinde\",\"count\":29}, "
            "{\"name\":\"Winter-Linde\",\"count\":22}]},\n"
            "  \"tier\": \"green\"\n"
            "}"},
        {"role": "assistant", "content":
            "The nearest official quiet zone, Volkspark Friedrichshain, sits "
            "620 metres from your door — a comfortable stroller walk. The park "
            "itself is 49 hectares, big enough for a full afternoon. Closer in, "
            "the block around the flat carries roughly 22 percent street-tree "
            "canopy — genuinely shady on a summer walk, with Gemeine Rosskastanie "
            "(horse-chestnut) and Kaiserlinde (linden) leading the local mix. For "
            "a young family this means daily walks stay green even before you "
            "reach the park, and the summer heat won't hit the pavement at "
            "full strength."},
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
        "trees": {"count": 150, "crown_coverage_pct": 18.2, "avg_age_yr": 35,
                  "top_species": [{"name": "Linde", "count": 40}]},
        "tier":  "green",
    })
    assert msgs[0]["role"] == "system"
    assert "quiet zone" in msgs[0]["content"].lower()
    assert "crown-coverage" in msgs[0]["content"].lower()
    assert "Test-Park" in msgs[-1]["content"]
    # No invention rule.
    assert "invent" in msgs[0]["content"].lower() or "fabricat" in msgs[0]["content"].lower()
    # Empty-both shortcut.
    empty = run(None, {"quiet": {}, "trees": {}})
    assert "walk it in person" in empty["insight"] or "hard signal" in empty["insight"].lower()
    print("refuge_insight.py selfcheck OK")
