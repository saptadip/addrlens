"""`arterial_road_insight` — distance-to-arterial gloss for the Quiet
Living lens.

Standalone template. Facts: single-anchor readout (name, class,
distance) from `Index.nearest_arterial`, or None when no arterial is
within the search radius.
"""
from __future__ import annotations

import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's arterial-road exposure signal for someone "
    "considering a specific flat and prioritising a calm home. You "
    "receive: the tier (green / amber / red), the rule, the numeric "
    "readout, and a metadata block with the nearest arterial's name, "
    "class ('I' = federal-tier, 'II' = arterial-tier), and distance "
    "in metres. When the block is null, no arterial road is within "
    "the search radius — treat that as a genuinely quiet residential "
    "block. Write ONE paragraph, 70–110 words, doing three things in "
    "order: "
    "(a) plain-English readout of the distance to the nearest arterial "
    "— under 50 metres is directly on the street, 50–150 m is "
    "block-adjacent, over 150 m is side-street territory; "
    "(b) practical framing: distance to arterial is a rough proxy for "
    "steady traffic noise, night-time truck passes, dust, and pram-safe "
    "pavements. Name the specific arterial when present; "
    "(c) honest closing sentence: at red distances the flat's façade "
    "orientation matters more than the address — a courtyard-facing "
    "unit reads differently from a street-facing one at the same door. "
    "Ground rules: no invented street names, no verdicts on the "
    "neighbourhood, English only except street names in German. "
    "Return only the paragraph."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
        "arterial": {
            "name":       ctx.get("name"),
            "class":      ctx.get("class"),
            "distance_m": ctx.get("distance_m"),
        } if ctx.get("distance_m") is not None else None,
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"tier\": \"amber\", \"rule\": \"50–149 m to nearest arterial\",\n"
            "  \"numeric\": \"80 m to Torstraße\",\n"
            "  \"arterial\": {\"name\":\"Torstraße\",\"class\":\"II\",\n"
            "                  \"distance_m\":80}\n"
            "}"},
        {"role": "assistant", "content":
            "The nearest arterial road, Torstraße, runs 80 metres from "
            "the flat — block-adjacent rather than directly on. That "
            "distance changes the noise profile noticeably: you'll "
            "hear the arterial as background rather than as the "
            "street outside your window, and daytime pram walks stay "
            "on quieter side streets. Truck and bus passes will still "
            "reach you at night when residential streets are silent. "
            "For a quiet-living audience the courtyard-facing side of "
            "a building at this distance often reads a full band "
            "quieter than the street-facing units — check which side "
            "the flat is on before signing."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "green", "rule": "≥ 150 m to nearest arterial",
        "numeric": "no arterial within search radius",
        "name": None, "class": None, "distance_m": None,
    })
    assert "arterial" in msgs[0]["content"].lower()
    assert "invent" in msgs[0]["content"].lower()
    print("arterial_road_insight.py selfcheck OK")
