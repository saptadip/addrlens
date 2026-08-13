"""`intl_food_insight` — plain-English gloss of the 'International food' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Framing is about weekly-shop convenience for newcomers, not restaurant
  nightlife or foodie culture.
- In the first weeks of a relocation, access to familiar ingredients and
  international grocers matters practically: cooking at home is cheaper
  and finding comfort foods eases the transition.
- No invented statistics or venue names.
- English only.
"""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret the international food and grocery proximity signal for a "
    "newcomer expat in Berlin. You receive: the tier (green / amber / red), "
    "the rule text, the numeric readout (count within radius), and a shortlist "
    "of the closest options each with name and distance in metres. Write ONE "
    "paragraph, 70–110 words, doing: "
    "(a) plain-English readout of how many international food options exist "
    "within walking distance and what that means for a weekly shop; "
    "(b) practical newcomer anchor: in the first weeks of a relocation, "
    "access to familiar ingredients from home-country cuisines matters — "
    "it makes cooking at home easier and cheaper, and finding comfort foods "
    "reduces transition fatigue; mention the nearest option by name if present; "
    "(c) honest closing note on what amber or red means for the weekly shop: "
    "fewer nearby options means a longer dedicated trip for international groceries. "
    "Ground rules: "
    "1. No invented statistics or venue names beyond the payload. "
    "2. No verdicts about the neighbourhood. No nightlife or restaurant framing. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
        "top":     (ctx.get("features") or [])[:5],
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        # One-shot: red tier — mainstream Rewe/Edeka territory
        {"role": "user", "content": (
            "{\n"
            "  \"tier\": \"red\", \"rule\": \"mainstream Rewe/Edeka territory\",\n"
            "  \"numeric\": \"1 international spot within 800 m walk\",\n"
            "  \"top\": [{\"name\": \"Netto\", \"distance_m\": 650}]\n"
            "}"
        )},
        {"role": "assistant", "content": (
            "Only mainstream German supermarkets appear within walking distance — "
            "your weekly shop for international ingredients will require a dedicated "
            "trip to a different part of the city. In the first weeks of a "
            "relocation this adds friction: cooking familiar recipes from home "
            "becomes a planned outing rather than a casual top-up. Factor a "
            "regular transit trip into your routine if variety in your weekly "
            "shop matters to you."
        )},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": (
            "No international food or grocery options found nearby. Your weekly "
            "shop for international ingredients will need a dedicated transit trip. "
            "Mainstream supermarkets (Rewe, Edeka, Lidl) are typically well-covered "
            "but stock limited international ranges."
        )}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "red", "rule": "mainstream Rewe/Edeka territory",
        "numeric": "1 international spot within 800 m walk",
        "features": [{"name": "Netto", "distance_m": 650}],
    })
    assert msgs[0]["role"] == "system"
    # System prompt mentions inversion rule
    assert "invert" in msgs[0]["content"].lower() or "never invert" in msgs[0]["content"].lower()
    # System prompt focuses on weekly-shop, not nightlife
    assert "weekly" in msgs[0]["content"].lower() or "weekly-shop" in msgs[0]["content"].lower(), \
        "system must mention weekly-shop framing"
    assert "nightlife" in msgs[0]["content"].lower() or "restaurant" in msgs[0]["content"].lower(), \
        "system must explicitly exclude nightlife framing"
    # Red exemplar must not positively invert
    exemplar_lower = msgs[2]["content"].lower()
    assert "trip" in exemplar_lower or "friction" in exemplar_lower, \
        "red exemplar must acknowledge the inconvenience"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    # Final user message
    assert msgs[-1]["role"] == "user"
    print("intl_food_insight.py selfcheck OK")
