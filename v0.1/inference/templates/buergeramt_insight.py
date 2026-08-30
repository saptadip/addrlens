"""`buergeramt_insight` — plain-English gloss of the 'Bürgeramt reach' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Bürgeramt proximity matters most for newcomers in the first 90 days:
  Anmeldung (address registration) and residence permit appointments are
  often the first mandatory tasks on arrival.
- Slots are bookable city-wide (Bürgeramt website + app), so a distant
  office is a fallback. Proximity matters for last-minute cancellation
  slots that appear 1–2 days out — you need to be able to walk there.
- No invented statistics. No invented names.
- English only, except 'Bürgeramt' and 'Anmeldung' which are proper
  terms the newcomer must learn.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's Bürgeramt (district registration office) proximity "
    "signal for a newcomer expat arriving in the first 90 days. You receive: "
    "the tier (green / amber / red), the rule text, the numeric readout "
    "(distance and name of nearest Bürgeramt), and a shortlist of the closest "
    "offices each with name and distance in metres. Write ONE paragraph, "
    "70–110 words, doing: "
    "(a) plain-English readout of how close the nearest Bürgeramt is and what "
    "that means in terms of a walk or transit ride; "
    "(b) practical newcomer anchor: Bürgeramt slots are bookable city-wide via "
    "Berlin's online booking system, so a distant office can still be used — "
    "but proximity matters for last-minute cancellation slots that open 1–2 days "
    "ahead; you need to be able to reach it on short notice; "
    "(c) honest closing note: Anmeldung (address registration) is typically the "
    "first appointment every newcomer must book — do this within 14 days of "
    "moving in. "
    "Ground rules: "
    "1. No invented statistics or office names beyond the payload. "
    "2. No verdicts about the neighbourhood. "
    "3. English only, except 'Bürgeramt' and 'Anmeldung' — proper terms the "
    "newcomer must learn. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"red\", \"rule\": \"cross-district trip required\",\n"
    "  \"numeric\": \"3800m to Bürgeramt Spandau\",\n"
    "  \"top\": [{\"name\": \"Bürgeramt Spandau\", \"distance_m\": 3800}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "The nearest Bürgeramt is 3.8 kilometres away — a cross-district trip, "
    "not a local walk. Slots are bookable city-wide online, so you can "
    "choose any Berlin Bürgeramt regardless of district, but last-minute "
    "cancellation slots that appear 1–2 days out require you to get there "
    "quickly — plan around transit time. Anmeldung (address registration) "
    "must be done within 14 days of moving in; book your slot before you "
    "arrive if you can."
)

_EMPTY_MSG = (
    "No Bürgeramt found in reachable range. Slots are bookable city-wide "
    "online, but factor in a significant transit journey. Book your Anmeldung "
    "(address registration) slot before you arrive — you must register "
    "within 14 days of moving in."
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
        "tier": "red", "rule": "cross-district trip required",
        "numeric": "3800m to Bürgeramt Spandau",
        "features": [{"name": "Bürgeramt Spandau", "distance_m": 3800}],
    })
    assert msgs[0]["role"] == "system"
    # System prompt mentions inversion rule
    assert "invert" in msgs[0]["content"].lower() or "never invert" in msgs[0]["content"].lower()
    # System prompt mentions Anmeldung
    assert "anmeldung" in msgs[0]["content"].lower()
    # One-shot exemplar is at position [1] (user) and [2] (assistant)
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"
    # Red-tier exemplar must not positively frame the outcome
    exemplar_lower = msgs[2]["content"].lower()
    assert "cross-district" in exemplar_lower or "trip" in exemplar_lower, \
        "red exemplar must acknowledge the difficulty"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    # Final user message contains the facts
    assert msgs[-1]["role"] == "user"
    assert "tier" in msgs[-1]["content"].lower() or "red" in msgs[-1]["content"].lower()
    print("buergeramt_insight.py selfcheck OK")
