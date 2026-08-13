"""`language_school_insight` — plain-English gloss of the 'German classes' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Frames B1-German as the practical unlock for Aufenthaltstitel and later
  Einbürgerung — the newcomer's structural gate, not a lifestyle enrichment.
- Distance-to-nearest is the driver; the paragraph must connect distance to
  attendance-rate reality (course finish rates track attendance).
- Do NOT recommend specific schools by name beyond what the payload names,
  and do NOT compare private Sprachschulen to VHS on cost or quality.
- English only.
"""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret the language-school proximity signal for a newcomer expat "
    "in Berlin in their first 90 days. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout (distance to nearest), and a "
    "shortlist of the closest Sprachschulen or Volkshochschule branches each "
    "with name and distance in metres. Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of how far the nearest option is; "
    "(b) practical newcomer framing: German B1 is the structural gate to the "
    "Aufenthaltstitel renewal and later Einbürgerung path, and course finish "
    "rates track attendance which tracks how close class is to home — mention "
    "the nearest name if present; "
    "(c) honest closing note on 'amber' or 'red': a longer commute to class "
    "adds friction that shows up as missed evenings in the middle of a busy "
    "settling-in period. "
    "Ground rules: "
    "1. No invented statistics or venue names beyond the payload. "
    "2. No comparison of VHS vs private Sprachschulen on price or quality. "
    "3. No promises about specific visa outcomes. "
    "4. English only. "
    "5. Never invert the meaning of a red tier into positive framing. "
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
        # One-shot: red tier — no nearby options
        {"role": "user", "content": (
            "{\n"
            "  \"tier\": \"red\", \"rule\": \"no Sprachschule or VHS branch nearby\",\n"
            "  \"numeric\": \"\",\n"
            "  \"top\": []\n"
            "}"
        )},
        {"role": "assistant", "content": (
            "No Sprachschule or Volkshochschule branch appears within a comfortable "
            "walk of this address. Because German B1 is the structural gate for the "
            "Aufenthaltstitel renewal and later Einbürgerung, missed evenings add up: "
            "a long commute to class in the middle of a busy relocation shows up as "
            "attendance drops, and attendance drives course finish rates more than "
            "motivation does. Plan a transit route to a branch you can reach in "
            "under thirty minutes, and budget the extra time on your calendar."
        )},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": (
            "No Sprachschule or Volkshochschule branch found nearby. German B1 is "
            "the structural gate for the Aufenthaltstitel renewal and later "
            "Einbürgerung, and a long commute to class turns into missed evenings "
            "during a busy relocation. Plan a transit route to a branch you can "
            "reach in under thirty minutes."
        )}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "red", "rule": "no Sprachschule or VHS branch nearby",
        "numeric": "", "features": [],
    })
    assert msgs[0]["role"] == "system"
    # System prompt mentions inversion rule
    assert "never invert" in msgs[0]["content"].lower()
    # System prompt frames B1 as the structural gate
    assert "b1" in msgs[0]["content"].lower() and "aufenthaltstitel" in msgs[0]["content"].lower(), \
        "system prompt must frame B1 as the structural gate"
    # One-shot red exemplar must not positively frame
    exemplar_lower = msgs[2]["content"].lower()
    assert "attendance" in exemplar_lower or "friction" in exemplar_lower or "commute" in exemplar_lower, \
        "red exemplar must acknowledge the difficulty"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    # Final user message
    assert msgs[-1]["role"] == "user"
    print("language_school_insight.py selfcheck OK")
