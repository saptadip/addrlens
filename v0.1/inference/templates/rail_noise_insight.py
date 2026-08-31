"""`rail_noise_insight` — rail-track proximity gloss for the Quiet
Living lens.

Standalone template. Facts: mode ('S-Bahn' | 'U-Bahn'), name,
distance_m from `Index.rail_track_proximity`. U-Bahn is treated as
always green because Berlin's U-Bahn runs underground on most
sections; S-Bahn scales by distance.
"""
from __future__ import annotations

import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's rail-track noise proxy for someone "
    "considering a specific flat and prioritising a calm home. You "
    "receive: the tier (green / amber / red), the rule, the numeric "
    "readout, and a metadata block with the nearest rail station's "
    "mode ('S-Bahn' or 'U-Bahn'), name, and distance in metres. Write "
    "ONE paragraph, 70–110 words, doing three things in order: "
    "(a) plain-English readout of the distance to the nearest S/U-Bahn "
    "station AS A PROXY for rail-track proximity — the tracks extend "
    "kilometres either side of a station, so the station coord "
    "understates the actual track length near the flat; "
    "(b) practical framing: S-Bahn is above ground and generates real "
    "façade noise; Berlin's U-Bahn is underground on most sections and "
    "produces very little street noise — mention which mode is nearest; "
    "(c) honest closing sentence: this is a rough signal. For an "
    "S-Bahn near the flat, walk the block at rush hour and check the "
    "façade orientation before signing. For a U-Bahn, ground vibration "
    "at ground-floor units is a separate risk not captured here. "
    "Ground rules: no invented station names, no verdicts, English only "
    "except S-Bahn / U-Bahn / Hochbahn. Return only the paragraph."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
        "rail": {
            "mode":       ctx.get("mode"),
            "name":       ctx.get("name"),
            "distance_m": ctx.get("distance_m"),
        } if ctx.get("distance_m") is not None else None,
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"tier\": \"amber\", \"rule\": \"S-Bahn 200–399 m away\",\n"
            "  \"numeric\": \"280 m to S-Bahn S Ostkreuz\",\n"
            "  \"rail\": {\"mode\":\"S-Bahn\",\"name\":\"S Ostkreuz\",\n"
            "             \"distance_m\":280}\n"
            "}"},
        {"role": "assistant", "content":
            "The nearest rail is S-Bahn Ostkreuz at 280 metres — an "
            "above-ground line, so the tracks either side of the "
            "station will carry real façade noise. That distance puts "
            "the flat inside audible range but not at the trackside "
            "extreme, so the pattern will read as pulses through the "
            "day rather than a continuous drone. For a quiet-living "
            "audience the relevant checks before signing are the "
            "flat's façade orientation (courtyard-facing units read "
            "a full band quieter) and whether the nearest track "
            "segment includes a bridge or a cut — bridges radiate "
            "more sound than embankments."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "green", "rule": "nearest rail is U-Bahn (underground)",
        "numeric": "40 m to U-Bahn U Turmstr.",
        "mode": "U-Bahn", "name": "U Turmstr.", "distance_m": 40,
    })
    assert "S-Bahn" in msgs[0]["content"] and "U-Bahn" in msgs[0]["content"]
    assert "invent" in msgs[0]["content"].lower()
    assert "U Turmstr." in msgs[-1]["content"]
    print("rail_noise_insight.py selfcheck OK")
