"""`bus_transit_insight` — plain-English gloss of the 'Bus Transit' tile
for the Newcomer lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Bus framing: last-mile access, groceries, night buses (N-lines) when
  the S-Bahn / U-Bahn stops running (~01:30 weekdays).
- A dense bus stop nearby is a genuine positive for a newcomer without a
  car; it complements rail rather than replacing it.
- No invented stop names. Preserve S-Bahn / U-Bahn / Tram / Bus as
  canonical modality terms.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's bus reachability signal for a newcomer expat "
    "arriving in the first 90 days. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout, and a shortlist of the "
    "nearest bus stops with name and distance in metres. Write ONE "
    "paragraph, 70–110 words, doing: "
    "(a) plain-English readout of the nearest bus stop and how long the "
    "walk is; "
    "(b) last-mile framing — buses handle groceries, cross-street routes "
    "the rail network skips, and the N-line night buses after the S/U "
    "shut down around 01:30 on weekdays; call out what a nearby bus "
    "practically enables; "
    "(c) honest note on amber or red — a longer walk to any bus stop is "
    "workable if rail is close, but real friction if it's not. "
    "Ground rules: "
    "1. No invented stop names — use only what the payload contains. "
    "2. Preserve S-Bahn / U-Bahn / Tram / Bus as canonical modality terms. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"bus at the doorstep\",\n"
    "  \"numeric\": \"40 m to Bus Emser Straße\",\n"
    "  \"top\": [{\"name\": \"Emser Straße\", \"distance_m\": 40}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "A bus stop sits about 40 metres from the door at Emser Straße. "
    "That means groceries and short cross-street errands are a "
    "one-stop hop rather than a walk, and Berlin's N-line night "
    "buses cover this address after the S-Bahn and U-Bahn shut down "
    "around 01:30 on weekdays. For a newcomer without a car it's a "
    "quiet quality-of-life multiplier — pair it with the rail tile "
    "to gauge how far you can reach on any single ticket."
)

_EMPTY_MSG = "No bus stop within walking distance."


def build_messages(ctx: dict) -> list[dict]:
    from inference.templates._insight_base import build_tier_messages
    return build_tier_messages(
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        ctx=ctx,
        top_k=6,
    )


def run(backend, ctx: dict) -> dict:
    return run_tier(
        backend, ctx,
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        empty_msg=_EMPTY_MSG,
        top_k=6,
    )


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "green", "rule": "bus at the doorstep",
        "numeric": "40 m to Bus Emser Straße",
        "features": [{"name": "Emser Straße", "distance_m": 40}],
    })
    assert msgs[0]["role"] == "system"
    assert "bus" in msgs[0]["content"].lower()
    assert "never invert" in msgs[0]["content"].lower()
    assert msgs[-1]["role"] == "user"
    print("bus_transit_insight.py selfcheck OK")
