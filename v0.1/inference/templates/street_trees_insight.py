"""`street_trees_insight` — canopy-coverage gloss for the Quiet Living
lens.

Standalone template (not scaffold-based) because the facts are aggregate
readings — count, crown %, top species — not a features shortlist.
Mirrors the shape of `heat_insight` / `noise_insight` / `air_insight`.
"""
from __future__ import annotations

import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's street-tree canopy signal for someone "
    "considering a specific flat and prioritising a calm home. You "
    "receive: the tier (green / amber / red), the rule, the numeric "
    "readout, and a metadata block with count, crown_coverage_pct, "
    "avg_age_yr, tallest_m, and top_species (list of {name, n}). "
    "Write ONE paragraph, 70–110 words, doing three things in order: "
    "(a) plain-English readout of the canopy percentage — under 15% is "
    "sparse, 15–25% moderate, above 25% genuinely shady; "
    "(b) practical framing for a quiet-living audience: dense mature "
    "street trees buffer road noise, drop summer heat, and change the "
    "quality of a morning walk. Mention the top species when present "
    "so the paragraph reads specific to the block; "
    "(c) one honest closing sentence when the tier is amber or red: "
    "sparse blocks are hotter and louder in summer, and a walk to "
    "the nearest tree-lined street becomes part of the daily routine. "
    "Ground rules: no invented statistics beyond the payload, no "
    "verdicts, English only except species names in German. "
    "Return only the paragraph."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
        "trees": {
            "count":              ctx.get("count"),
            "crown_coverage_pct": ctx.get("crown_coverage_pct"),
            "avg_age_yr":         ctx.get("avg_age_yr"),
            "tallest_m":          ctx.get("tallest_m"),
            "top_species":        (ctx.get("top_species") or [])[:5],
        },
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"tier\": \"green\", \"rule\": \"canopy ≥ 25%\",\n"
            "  \"numeric\": \"28% canopy across 187 trees\",\n"
            "  \"trees\": {\"count\": 187, \"crown_coverage_pct\": 28.4,\n"
            "     \"avg_age_yr\": 41, \"tallest_m\": 22,\n"
            "     \"top_species\": [\n"
            "       {\"name\": \"Gemeine Rosskastanie\", \"n\": 38},\n"
            "       {\"name\": \"Winter-Linde\", \"n\": 29}\n"
            "     ]}\n"
            "}"},
        {"role": "assistant", "content":
            "The block around the flat carries roughly 28% street-tree "
            "canopy — genuinely shady on a summer walk, and the average "
            "trunk is forty years old, so the shade is stable rather "
            "than seasonal. Gemeine Rosskastanie (horse-chestnut) and "
            "Winter-Linde (small-leaved linden) lead the mix, both good "
            "at buffering road noise and dropping the pavement "
            "temperature. For a quiet-living audience this matters "
            "twice: the trees soften the acoustic environment, and "
            "they make the daily walk to transit feel calm even before "
            "you reach a park."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if ctx.get("crown_coverage_pct") is None:
        return {"insight": "No street-tree data recorded for this block."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "amber", "rule": "canopy 15–24%",
        "numeric": "18% canopy across 90 trees",
        "count": 90, "crown_coverage_pct": 18.2, "avg_age_yr": 32,
        "top_species": [{"name": "Linde", "n": 40}],
    })
    assert "canopy" in msgs[0]["content"].lower()
    assert "invent" in msgs[0]["content"].lower()
    assert "Linde" in msgs[-1]["content"]
    print("street_trees_insight.py selfcheck OK")
