"""`cycling_network_insight` — plain-English gloss of the 'Cycling
network reach' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Reads the OSM `highway=cycleway` bucket — dedicated infrastructure
  only. The tile's caveat covers the painted-lane exclusion; the
  prompt reinforces it so the model doesn't over-claim.
- No invented cycleway names. English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's dedicated-cycleway reachability signal for "
    "a reader who might commute by bike. You receive: the tier "
    "(green / amber / red), the rule text, the numeric readout, and a "
    "shortlist of the nearest cycleway centroids with (optional) name "
    "and distance in metres. Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of the nearest dedicated cycleway and "
    "how long the walk (or short push) to reach it is; "
    "(b) commuter framing — a nearby dedicated cycleway means the "
    "commute can begin on protected infrastructure rather than mixed "
    "traffic, which is the single biggest quality signal for daily "
    "bike commuting in Berlin. The data covers dedicated cycleways "
    "only (OSM `highway=cycleway`); painted bike lanes on shared "
    "roads are NOT reflected in the signal; "
    "(c) honest note on amber or red — the commute can still work by "
    "bike but the first few blocks will share the road with cars. "
    "Ground rules: "
    "1. No invented cycleway names — use only what the payload contains. "
    "2. Be explicit that this reflects dedicated infrastructure, not "
    "painted lanes on shared roads. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"dedicated cycleway on the doorstep\",\n"
    "  \"numeric\": \"60 m to nearest cycleway\",\n"
    "  \"top\": [{\"name\": \"\", \"distance_m\": 60}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "A dedicated cycleway sits about 60 metres from the door. That "
    "means the daily commute can begin on protected infrastructure "
    "rather than mixed traffic — the biggest quality signal for bike "
    "commuting in Berlin. The data covers OSM `highway=cycleway` only, "
    "so painted lanes on shared roads are not part of this tile; the "
    "actual coverage from door to office may be higher than the "
    "signal suggests. Pair with the arterial-road tile from the Quiet "
    "Living lens to see whether the ride starts on a busy street."
)

_EMPTY_MSG = "No dedicated cycleway near this address in the current snapshot."


def build_messages(ctx: dict) -> list[dict]:
    from inference.templates._insight_base import build_tier_messages
    return build_tier_messages(
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        ctx=ctx,
        top_k=5,
    )


def run(backend, ctx: dict) -> dict:
    return run_tier(
        backend, ctx,
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        empty_msg=_EMPTY_MSG,
        top_k=5,
    )


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "green", "rule": "dedicated cycleway on the doorstep",
        "numeric": "60 m to nearest cycleway",
        "features": [{"name": "", "distance_m": 60}],
    })
    sys_low = msgs[0]["content"].lower()
    # Caveat about painted lanes is load-bearing — the OSM signal is
    # narrower than "any bike infrastructure" and the model must say so.
    assert "painted" in sys_low, \
        "system must flag that painted lanes are not in the signal"
    assert "dedicated" in sys_low
    assert "never invert" in sys_low
    print("cycling_network_insight.py selfcheck OK")
