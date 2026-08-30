"""`coworking_insight` — plain-English gloss of the 'Coworking + Wi-Fi cafés' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Newcomers often need a laptop-friendly anchor in the first weeks
  before a permanent desk or home office is set up.
- Framing is about first-month practical anchor, not long-term remote work
  lifestyle or café nightlife.
- No invented statistics or venue names.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret the coworking and laptop-friendly café proximity signal "
    "for a newcomer expat in Berlin in their first 90 days. You receive: "
    "the tier (green / amber / red), the rule text, the numeric readout "
    "(count within radius), and a shortlist of the closest options each "
    "with name and distance in metres. Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of how many options exist and how close they are; "
    "(b) practical newcomer anchor: before a permanent desk or home office is "
    "set up, a walkable coworking space or Wi-Fi café is a first-month lifeline "
    "for staying productive — mention the nearest name if present; "
    "(c) honest closing note on what 'amber' or 'red' means in practice: "
    "fewer nearby options means a longer commute to a desk during the "
    "settling-in period, which adds friction when there are many other tasks. "
    "Ground rules: "
    "1. No invented statistics or venue names beyond the payload. "
    "2. No verdicts about the neighbourhood, no restaurant nightlife framing. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"red\", \"rule\": \"no laptop-friendly options nearby\",\n"
    "  \"numeric\": \"0 remote-work spots within 1000 m\",\n"
    "  \"top\": []\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "No coworking spaces or Wi-Fi cafés appear within a kilometre of this "
    "address. In the first weeks before your home office is set up, that "
    "means a transit ride to find a desk — adding friction at the busiest "
    "point of a relocation. Factor a coworking day-pass budget and commute "
    "time into your first-month plan if remote work is part of your routine."
)

_EMPTY_MSG = (
    "No coworking spaces or Wi-Fi cafés found nearby. During your first "
    "weeks before a permanent desk is arranged, plan for a transit journey "
    "to reach a laptop-friendly workspace."
)


def build_messages(ctx: dict) -> list[dict]:
    from inference.templates._insight_base import build_tier_messages
    return build_tier_messages(
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        ctx=ctx,
    )


def run(backend, ctx: dict) -> dict:
    return run_tier(
        backend, ctx,
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        empty_msg=_EMPTY_MSG,
    )


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "red", "rule": "no laptop-friendly options nearby",
        "numeric": "0 remote-work spots within 1000 m",
        "features": [],
    })
    assert msgs[0]["role"] == "system"
    # System prompt mentions inversion rule
    assert "invert" in msgs[0]["content"].lower() or "never invert" in msgs[0]["content"].lower()
    # System prompt focuses on practical newcomer anchor, not nightlife
    assert "nightlife" in msgs[0]["content"].lower() or "restaurant" in msgs[0]["content"].lower() or \
           "first-month" in msgs[0]["content"].lower(), \
        "system prompt must mention the first-month anchor and exclude nightlife framing"
    # One-shot red exemplar must not positively frame
    exemplar_lower = msgs[2]["content"].lower()
    assert "transit" in exemplar_lower or "friction" in exemplar_lower, \
        "red exemplar must acknowledge the difficulty"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    # Final user message
    assert msgs[-1]["role"] == "user"
    print("coworking_insight.py selfcheck OK")
