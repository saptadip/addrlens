"""`heat_insight` — 'Summer heat' tile gloss (Umweltatlas bioklima 2022)."""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's summer-heat bioclimate signal for an "
    "English-speaking expat. Source is the Umweltatlas 'Bioklima Tag' 2022 "
    "layer, which classifies each block by physiologically equivalent "
    "temperature (PET) at 14:00 in summer. Class strings are German — for "
    "instance 'geringe Belastung' (low burden), 'mäßige Belastung' "
    "(moderate), 'starke Belastung' (heavy), 'extreme Belastung' (extreme). "
    "You receive: the class string, the tier, and the rule text. "
    "Write ONE paragraph, 70–110 words: "
    "(a) plain-English translation of the class into what a family will "
    "actually feel — a mäßige-Belastung block still gets hot; a "
    "starke-Belastung block regularly hits PET 33–35 °C on summer "
    "afternoons; extreme-Belastung is where sleep disturbance sets in; "
    "(b) daily-life anchors that mitigate: cross-ventilation between "
    "street and courtyard windows, external shutters or awnings, and "
    "nearby street-tree canopy all reduce the felt heat far more than "
    "the score suggests; "
    "(c) close on child-specific advice: infants and toddlers dehydrate "
    "faster; on the two or three worst heatwave days each summer, plan "
    "for the coolest room in the flat and daytime shade routes to the "
    "playground. "
    "No invented numbers beyond what the class implies. English only, "
    "but preserve 'Belastung' verbatim (it's a term the user will see "
    "on every official Berlin document). Return the paragraph only."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "class":   ctx.get("class") or ctx.get("day_class"),
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"class\":\"> 33 °C - <= 35 °C - mäßige Belastung\","
            "\"tier\":\"amber\",\n"
            "  \"rule\":\"mäßige / starke Belastung\",\n"
            "  \"numeric\":\"> 33 °C - <= 35 °C - mäßige Belastung\"\n"
            "}"},
        {"role": "assistant", "content":
            "Your block sits in the mäßige-Belastung band — moderate summer "
            "heat burden, with a physiologically equivalent temperature "
            "typically between 33 and 35 °C on hot afternoons. Warm rather "
            "than punishing on the average summer day, but the two or three "
            "peak heatwave afternoons each year will genuinely test the "
            "flat. Cross-ventilation between the street façade and courtyard "
            "windows helps more than an air-conditioner ever will in "
            "Berlin; external shutters if the flat has them, and street-tree "
            "canopy on the walk to the playground, matter noticeably. With "
            "a toddler, pre-plan the coolest room and shaded daytime routes."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("class") or ctx.get("day_class")):
        return {"insight": "No summer-heat classification available for this address."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({"class": "mäßige Belastung"})
    assert "Umweltatlas" in msgs[0]["content"]
    assert "Belastung" in msgs[0]["content"]
    print("heat_insight.py selfcheck OK")
