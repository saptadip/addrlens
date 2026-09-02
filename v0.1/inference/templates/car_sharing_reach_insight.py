"""`car_sharing_reach_insight` — plain-English gloss of the
'Car-sharing reach' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Reads the OSM `amenity=car_sharing` bucket — fixed pickup points
  (SHARE NOW, Miles, WeShare stations). Free-float zones are NOT
  modelled; the prompt reinforces this so the model doesn't
  over-claim.
- Framing: occasional car use for weekly errands or the odd trip out
  of town, not the daily commute.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's car-sharing station density signal for a "
    "reader whose daily commute is mostly transit-based but who may "
    "need occasional car access. You receive: the tier (green / amber "
    "/ red), the rule text, the numeric readout (count within a fixed "
    "radius), and a shortlist of the nearest car-sharing pickup "
    "points with (optional) operator name and distance in metres. "
    "Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout — how many stations sit within the "
    "walking radius; "
    "(b) commuter framing — car-sharing is for the weekly IKEA run, "
    "the trip out of the city on a weekend, or the emergency airport "
    "run — not the daily commute. A cluster of nearby stations means "
    "car access is possible without owning a car. Data covers fixed "
    "pickup points only (OSM `amenity=car_sharing`); free-float zones "
    "from SHARE NOW / Miles / WeShare are NOT reflected; "
    "(c) honest note on amber or red — occasional car use will "
    "require a walk to reach a station. "
    "Ground rules: "
    "1. No invented operator names — use only what the payload contains. "
    "2. Be explicit that free-float zones are not part of this signal. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"multiple car-sharing pickup points within reach\",\n"
    "  \"numeric\": \"4 stations within 500 m\",\n"
    "  \"top\": [{\"name\": \"SHARE NOW\", \"distance_m\": 180}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "Four car-sharing pickup points sit within 500 metres of the door, "
    "the nearest at about 180 metres. That's enough density to make "
    "car access practical without owning a car: the weekly IKEA run, "
    "the weekend trip out of the city, or the odd airport run for a "
    "family arrival. This tile covers fixed pickup points only, so "
    "any free-float zones from SHARE NOW / Miles / WeShare would add "
    "coverage on top. For everyday commuting, the transit tiles "
    "carry more weight."
)

_EMPTY_MSG = "No car-sharing pickup point within walking distance."


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
        "tier": "green", "rule": "multiple car-sharing pickup points within reach",
        "numeric": "4 stations within 500 m",
        "features": [{"name": "SHARE NOW", "distance_m": 180}],
    })
    sys_low = msgs[0]["content"].lower()
    # Load-bearing: free-float caveat must be present.
    assert "free-float" in sys_low or "free float" in sys_low, \
        "system must flag that free-float zones are not part of the signal"
    assert "never invert" in sys_low
    print("car_sharing_reach_insight.py selfcheck OK")
