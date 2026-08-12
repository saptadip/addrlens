"""`air_insight` — 'Air quality (NO₂)' tile gloss."""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's NO₂ air-quality signal for an "
    "English-speaking expat. Source is the Umweltatlas Luftreinhalteplan "
    "2018–2025 trend-scenario modelled at street-segment resolution. "
    "You receive: NO₂ concentration in µg/m³, the tier, and the rule. "
    "Reference thresholds: WHO 2021 annual guideline is 10 µg/m³; the EU "
    "and German legal limit is 40 µg/m³. "
    "Write ONE paragraph, 70–110 words: "
    "(a) plain-English readout of the µg/m³ value against BOTH the WHO "
    "guideline and the legal limit — many Berlin blocks now sit below the "
    "legal limit but well above the WHO recommendation, and expats deserve "
    "to know both numbers; "
    "(b) dominant source in this city is road traffic (diesel legacy), so "
    "distance from the nearest main road matters more than the score "
    "suggests — mention that the model output is per street segment, so "
    "the courtyard side of a building typically reads better than the "
    "façade; "
    "(c) child-specific anchor: NO₂ long-term exposure is linked to "
    "childhood-asthma incidence — for a young family this argues for the "
    "courtyard side of the building and closed windows during rush hour "
    "on the loudest days. "
    "No invented numbers. English only, preserve 'µg/m³' notation. Return "
    "the paragraph only."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "ugm3":    ctx.get("ugm3") or ctx.get("no2_ugm3"),
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"ugm3\": 21.61, \"tier\": \"amber\",\n"
            "  \"rule\": \"NO₂ 20–40 µg/m³\",\n"
            "  \"numeric\": \"21.61 µg/m³ NO₂\"\n"
            "}"},
        {"role": "assistant", "content":
            "The modelled NO₂ at this street segment is 21.61 µg/m³ — "
            "comfortably below the EU legal limit of 40 µg/m³, but still "
            "roughly twice the WHO 2021 annual guideline of 10 µg/m³. That "
            "gap is typical of the Berlin inner ring today. Road traffic "
            "remains the dominant source in the city, so the courtyard side "
            "of the building will normally read materially better than the "
            "street façade — the model reports one number per segment, not "
            "one per apartment. Long-term NO₂ exposure is linked to "
            "childhood-asthma incidence, so for a young family favour the "
            "courtyard side and close windows during rush hour on the "
            "busiest days."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    val = ctx.get("ugm3") or ctx.get("no2_ugm3")
    if val is None:
        return {"insight": "No NO₂ reading available for this address."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({"ugm3": 22.0, "tier": "amber"})
    assert "NO₂" in msgs[0]["content"] or "NO2" in msgs[0]["content"]
    assert "WHO" in msgs[0]["content"]
    assert "invent" in msgs[0]["content"].lower()
    print("air_insight.py selfcheck OK")
