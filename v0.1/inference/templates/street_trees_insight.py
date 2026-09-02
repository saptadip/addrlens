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
    "(a) plain-English readout of the canopy percentage. Berlin's "
    "Baumbestand dataset tracks registered street trees ONLY (not park "
    "or private-garden trees), and the metric divides crown-disk area "
    "by the whole search-disk area — most of that disk is buildings, "
    "so real Berlin residential streets rarely exceed the low teens. "
    "Frame the number on that scale: under 5% is sparse, 5–10% "
    "moderate, above 10% clearly tree-dense for a Straßenbäume-only "
    "signal; "
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
            "  \"tier\": \"green\", \"rule\": \"canopy ≥ 10%\",\n"
            "  \"numeric\": \"11.4% canopy across 199 trees\",\n"
            "  \"trees\": {\"count\": 199, \"crown_coverage_pct\": 11.4,\n"
            "     \"avg_age_yr\": 41, \"tallest_m\": 22,\n"
            "     \"top_species\": [\n"
            "       {\"name\": \"Gemeine Rosskastanie\", \"n\": 38},\n"
            "       {\"name\": \"Winter-Linde\", \"n\": 29}\n"
            "     ]}\n"
            "}"},
        {"role": "assistant", "content":
            "The block around the flat carries roughly 11% street-tree "
            "canopy — clearly tree-dense for a Straßenbäume-only signal, "
            "and the average trunk is forty years old, so the shade is "
            "stable rather than seasonal. Gemeine Rosskastanie "
            "(horse-chestnut) and Winter-Linde (small-leaved linden) "
            "lead the mix, both good at buffering road noise and "
            "dropping the pavement temperature. For a quiet-living "
            "audience this matters twice: the trees soften the acoustic "
            "environment, and they make the daily walk to transit feel "
            "calm even before you reach a park."},
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
        "tier": "amber", "rule": "canopy 5–9%",
        "numeric": "6.8% canopy across 90 trees",
        "count": 90, "crown_coverage_pct": 6.8, "avg_age_yr": 32,
        "top_species": [{"name": "Linde", "n": 40}],
    })
    sys_low = msgs[0]["content"].lower()
    assert "canopy" in sys_low
    # System prompt now names the Straßenbäume-only limitation and the
    # 5 / 10 % calibration. Guard against a regression that would
    # re-introduce the physically unreachable 25 / 15 % numbers.
    assert "straßenbäume" in sys_low or "strassenbaume" in sys_low or \
           "street tree" in sys_low
    assert "5%" in msgs[0]["content"] and "10%" in msgs[0]["content"], \
        "system must anchor the retuned 5 / 10 % scale (as `%` glyph)"
    assert "5 percent" not in sys_low and "10 percent" not in sys_low, \
        "system must use `%` glyph, not spelled-out 'percent' (parity with refuge_insight)"
    assert "25%" not in msgs[0]["content"] and "15%" not in msgs[0]["content"], \
        "system must not carry the stale 25 / 15 % anchors"
    # Green exemplar rule must be `canopy ≥ 10%` (was `≥ 25%`).
    ex_rule = msgs[1]["content"]
    assert "≥ 10%" in ex_rule or "canopy ≥ 10%" in ex_rule
    assert "25%" not in ex_rule
    assert "Linde" in msgs[-1]["content"]
    print("street_trees_insight.py selfcheck OK")
