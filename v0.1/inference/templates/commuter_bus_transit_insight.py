"""`commuter_bus_transit_insight` — plain-English gloss of the 'Bus
reach' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Commuter framing: bus is the fill-in for the daily commute — closes
  the last-mile where the S / U / Tram network thins, especially in
  outer districts, and provides the N-line night option after the
  S/U shut down.
- No invented stop names. Preserve S-Bahn / U-Bahn / Tram / Bus.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's bus reachability signal for a reader who "
    "commutes daily. You receive: the tier (green / amber / red), the "
    "rule text, the numeric readout, and a shortlist of the nearest "
    "bus stops with name and distance in metres. Write ONE paragraph, "
    "70–110 words, doing: "
    "(a) plain-English readout of the nearest bus stop and how long "
    "the walk is; "
    "(b) commuter framing — buses fill the last-mile gap between home "
    "and the nearest S / U / Tram, especially in outer districts. The "
    "N-line night buses cover the same route after the rail network "
    "shuts down around 01:30 on weekdays, so a nearby bus stop is "
    "insurance for late shifts and evening returns; "
    "(c) honest note on amber or red — a further walk to any bus is "
    "workable if S / U / Tram is close, but a real cost twice a day. "
    "Ground rules: "
    "1. No invented stop names — use only what the payload contains. "
    "2. Preserve S-Bahn / U-Bahn / Tram / Bus as canonical modality terms. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"amber\", \"rule\": \"bus a few minutes away\",\n"
    "  \"numeric\": \"420 m to Bus Petersburger Str.\",\n"
    "  \"top\": [{\"name\": \"Petersburger Str.\", \"distance_m\": 420}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "The nearest bus stop is about 420 metres away at Petersburger "
    "Str. — a five-to-six minute walk. That's workable as a last-mile "
    "backup when the S / U or Tram is the primary daily ride, and the "
    "N-line night bus on the same corridor covers late shifts after "
    "the rail network stops around 01:30 on weekdays. Twice a day the "
    "extra minutes will add up, so lean on the rail tile to see "
    "whether the commute leans on bus or rail as its main mode."
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
        "tier": "amber", "rule": "bus a few minutes away",
        "numeric": "420 m to Bus Petersburger Str.",
        "features": [{"name": "Petersburger Str.", "distance_m": 420}],
    })
    sys_low = msgs[0]["content"].lower()
    assert "bus" in sys_low and "daily" in sys_low and "commute" in sys_low
    assert "never invert" in sys_low
    # Amber exemplar must not falsely praise a further walk.
    ex_low = msgs[2]["content"].lower()
    assert "excellent" not in ex_low and "great location" not in ex_low
    print("commuter_bus_transit_insight.py selfcheck OK")
