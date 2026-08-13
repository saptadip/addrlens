"""`wochenmarkt_insight` — plain-English gloss of the 'Wochenmarkt' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Frames the Wochenmarkt as a low-barrier settling-in ritual for newcomers:
  cash-friendly, no-German-required point-and-pay, mixed international vendors,
  and a weekly rhythm that turns a neighbourhood into 'home'.
- OSM `amenity=marketplace` does not distinguish food markets from flea markets;
  the template must acknowledge that a nearby match might be a Trödelmarkt rather
  than a food market, and not overpromise fresh produce.
- Do NOT invent specific vendor claims or opening days beyond the payload.
- English only.
"""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret the weekly-market proximity signal for a newcomer expat "
    "in Berlin in their first 90 days. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout (distance to nearest), and a "
    "shortlist of the closest markets each with name and distance in metres. "
    "Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of how far the nearest market is; "
    "(b) practical newcomer framing: a Wochenmarkt is a low-barrier settling-in "
    "ritual — cash-friendly, no-German-required point-and-pay, international "
    "vendors — and the weekly rhythm turns a neighbourhood into home faster "
    "than a single supermarket run — mention the nearest name if present; "
    "(c) honest caveat: the underlying data does not distinguish food markets "
    "from Trödelmärkte (flea markets), so a very close match may be a flea "
    "market rather than a food market — worth a quick check on foot; "
    "(d) honest closing note on 'amber' or 'red': the further the market, the "
    "less likely the weekly-visit habit forms. "
    "Ground rules: "
    "1. No invented vendor names, produce claims, or opening days. "
    "2. Do not overpromise fresh produce when a match may be a flea market. "
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
        {"role": "user", "content": (
            "{\n"
            "  \"tier\": \"red\", \"rule\": \"no registered Wochenmarkt nearby\",\n"
            "  \"numeric\": \"\",\n"
            "  \"top\": []\n"
            "}"
        )},
        {"role": "assistant", "content": (
            "No registered Wochenmarkt appears within a comfortable walk of this "
            "address. That is a real loss in the first months: a weekly market "
            "is one of the low-barrier settling-in rituals a newcomer can pick "
            "up without German — cash, point, pay — and the weekly rhythm turns "
            "a neighbourhood into home faster than any supermarket run. Without "
            "one nearby, the habit takes an extra transit trip and rarely sticks. "
            "Check whether any market is on a route you already take, or accept "
            "that Rewe and Edeka will carry the week for now."
        )},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": (
            "No registered Wochenmarkt found nearby. A weekly market is a "
            "low-barrier settling-in ritual — cash, point, pay, no German needed. "
            "Without one nearby, the habit takes an extra transit trip and rarely "
            "sticks. Check whether any market is on a route you already take."
        )}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "red", "rule": "no registered Wochenmarkt nearby",
        "numeric": "", "features": [],
    })
    assert msgs[0]["role"] == "system"
    assert "never invert" in msgs[0]["content"].lower()
    # System prompt must call out the flea-vs-food ambiguity
    assert "trödelmarkt" in msgs[0]["content"].lower() or "flea" in msgs[0]["content"].lower(), \
        "system prompt must acknowledge flea-market ambiguity"
    exemplar_lower = msgs[2]["content"].lower()
    assert "transit" in exemplar_lower or "supermarket" in exemplar_lower or "rewe" in exemplar_lower, \
        "red exemplar must acknowledge the settling-in gap"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    assert msgs[-1]["role"] == "user"
    print("wochenmarkt_insight.py selfcheck OK")
