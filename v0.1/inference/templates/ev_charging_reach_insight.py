"""`ev_charging_reach_insight` — plain-English gloss of the 'EV charger
reach' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Reads the OSM `ev_charging` bucket. Not every charger is publicly
  usable; the prompt notes that OSM coverage is uneven for private
  chargers and that stated kW is a claim, not a certified rating.
- Framing: EV owners commuting daily who charge at home vs. rely on
  street chargers.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's public EV-charger density signal for a "
    "reader who commutes with an electric car. You receive: the tier "
    "(green / amber / red), the rule text, the numeric readout (count "
    "within a fixed radius), and a shortlist of the nearest chargers "
    "with (optional) operator name and distance in metres. Write ONE "
    "paragraph, 70–110 words, doing: "
    "(a) plain-English readout — how many chargers sit within the "
    "walking radius; "
    "(b) commuter framing — the tile matters mainly if the reader "
    "does not have home charging: overnight top-ups at a nearby "
    "street charger keep the daily commute practical. If home "
    "charging is available, this tile is less load-bearing; "
    "(c) honest caveat — the OSM coverage of chargers is uneven and "
    "operator status (public vs. private) is not always tagged; "
    "confirm access on the operator's app before relying on a "
    "specific station. "
    "Ground rules: "
    "1. No invented operator names — use only what the payload contains. "
    "2. Do not guarantee that a charger is public or working. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"amber\", \"rule\": \"one EV charger within reach\",\n"
    "  \"numeric\": \"1 charger within 500 m\",\n"
    "  \"top\": [{\"name\": \"Allego\", \"distance_m\": 340}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "One EV charger sits within 500 metres of the door, the closest "
    "at about 340 metres. For a daily commute without home charging, "
    "a single station is workable but adds friction: an overnight "
    "top-up depends on one specific plug being free, and outages can "
    "compound. OSM coverage of charger status is uneven, so confirm "
    "public access and current kW on the operator's app before "
    "relying on the station. Home charging, where available, "
    "shifts the daily-commute weight of this tile."
)

_EMPTY_MSG = "No EV charger within walking distance."


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
        "tier": "amber", "rule": "one EV charger within reach",
        "numeric": "1 charger within 500 m",
        "features": [{"name": "Allego", "distance_m": 340}],
    })
    sys_low = msgs[0]["content"].lower()
    # Load-bearing caveat: OSM coverage / status uncertainty.
    assert "osm" in sys_low
    assert "confirm" in sys_low
    assert "never invert" in sys_low
    print("ev_charging_reach_insight.py selfcheck OK")
