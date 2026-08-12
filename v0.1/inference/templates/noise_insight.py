"""`noise_insight` template — plain-English gloss of the Young Family
'Façade noise' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Same per-card naming convention as gesix_insight / refuge_insight.
- Context payload: l_den + l_night dB values (total + per-source
  breakdown into road / rail / air) plus the derived tier.
- WHO recommends ≤55 dB L_DEN in residential; ≥60 dB is linked to sleep
  disturbance. Berlin's action-plan trigger is 70 dB.
- Anchor on the DOMINANT source (road vs rail vs air) — parents care
  about which side of the flat is loud.
- End with a concrete morning-vs-night comparison since young children's
  sleep is the pressure point.
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
    "You interpret Berlin's façade-noise reading for an English-speaking "
    "expat considering a specific flat. You receive: L_DEN (24-hour "
    "day-evening-night average, dB), L_night (22:00–06:00 average, dB), "
    "each broken into total / road / rail / air source contribution, plus "
    "the derived tier. Write ONE paragraph, 70–110 words, doing three "
    "things in order: "
    "(a) plain-English readout of L_DEN vs the WHO 55 dB residential "
    "guideline — ≤55 dB is quiet, 55–60 dB moderate, 60–65 dB busy, "
    ">65 dB loud; state whether Berlin's 70 dB action-plan trigger is met; "
    "(b) name the dominant source (road, rail, or air) by picking the "
    "largest per-source value in the payload and describe what that means "
    "day-to-day (road = constant hum, rail = periodic peaks, air = "
    "predictable flight windows); "
    "(c) morning-vs-night contrast using L_night vs L_DEN — if the delta "
    "is small the block is loud around the clock; if large, night is "
    "relatively quiet. Close on the practical anchor a young family cares "
    "about: whether it will affect a child's sleep and where in the flat "
    "the bedroom should sit. "
    "Ground rules: "
    "1. No invented numbers. Only reference dB values present in the "
    "payload. Do not fabricate distance to any specific road or rail line. "
    "2. No 'good' / 'bad' verdicts. Describe consequences, not judgements. "
    "3. English only. Preserve 'L_DEN' and 'L_night' as proper terminology. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "l_den":   ctx.get("l_den") or {},
        "l_night": ctx.get("l_night") or {},
        "tier":    ctx.get("tier"),
    }, ensure_ascii=False, indent=2)

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"l_den\":   {\"total\": 63.8, \"road\": 63.5, \"rail\": 47.2, \"air\": 42.0},\n"
            "  \"l_night\": {\"total\": 55.1, \"road\": 55.0, \"rail\": 44.6, \"air\": 40.1},\n"
            "  \"tier\":    \"amber\"\n"
            "}"},
        {"role": "assistant", "content":
            "The façade L_DEN reading is 63.8 dB — clearly above the WHO 55 dB "
            "residential guideline and squarely in the busy band, but still "
            "below Berlin's 70 dB action-plan trigger. Road traffic dominates "
            "at 63.5 dB while rail and air stay in the 40s, so the noise you "
            "hear is the constant background hum of nearby motor traffic rather "
            "than periodic peaks. L_night drops to 55.1 dB, roughly 8 dB below "
            "the daytime figure — the block does calm down after 22:00, but "
            "it never becomes truly quiet. For a young family, place the "
            "child's bedroom on the courtyard side rather than the street "
            "façade."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    total = ((ctx.get("l_den") or {}).get("total"))
    if total is None:
        return {"insight": "No façade-noise reading available for this address."}
    msgs = build_messages(ctx)
    text = backend.generate_from_messages(msgs, **SAMPLER)
    return {"insight": text}


if __name__ == "__main__":
    msgs = build_messages({
        "l_den":   {"total": 63.8, "road": 63.5, "rail": 47.2, "air": 42.0},
        "l_night": {"total": 55.1, "road": 55.0, "rail": 44.6, "air": 40.1},
        "tier":    "amber",
    })
    assert msgs[0]["role"] == "system"
    assert "L_DEN" in msgs[0]["content"]
    assert "63.8" in msgs[-1]["content"]
    assert "invent" in msgs[0]["content"].lower() or "fabricat" in msgs[0]["content"].lower()
    empty = run(None, {"l_den": {}})
    assert "not available" in empty["insight"].lower() or "no fa" in empty["insight"].lower()
    print("noise_insight.py selfcheck OK")
