"""`regional_rail_reach_insight` — plain-English gloss of the
'Regional rail reach' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Focus: RE / RB reachability for a commuter whose workday may lie
  outside inner Berlin — Potsdam, Bernau, Erkner, or occasional
  regional trips. Distinct from the S/U tile because the RE/RB
  network has fewer stations and thicker headways; missing your
  train is a bigger cost.
- No invented station names. Preserve S-Bahn / U-Bahn / RE / RB.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's regional-rail (RE / RB) reachability signal "
    "for a reader whose daily or weekly commute may leave inner Berlin. "
    "You receive: the tier (green / amber / red), the rule text, the "
    "numeric readout, and a shortlist of the nearest RE / RB stations "
    "with name and distance in metres. Write ONE paragraph, 70–110 "
    "words, doing: "
    "(a) plain-English readout of the nearest regional-rail station "
    "and how long the walk is; "
    "(b) commuter framing — the RE / RB network has fewer stations "
    "and longer headways than the S-Bahn, so proximity matters more: "
    "missing your train costs 20–30 minutes, not 5. Regional trains "
    "are the daily commute for anyone whose workplace sits in Potsdam, "
    "Bernau, Königs Wusterhausen, or the wider Berlin-Brandenburg "
    "region; "
    "(c) honest note on amber or red — a distant regional-rail "
    "station means a bus or tram interchange twice a day, which "
    "compounds. "
    "Ground rules: "
    "1. No invented station names — use only what the payload contains. "
    "2. Preserve S-Bahn / U-Bahn / RE / RB as canonical modality terms. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"regional-rail station within short walk\",\n"
    "  \"numeric\": \"850 m to Ostkreuz\",\n"
    "  \"top\": [{\"name\": \"Ostkreuz\", \"distance_m\": 850}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "Ostkreuz sits about 850 metres from the door — a ten-minute walk "
    "to a station on the regional-rail network. That matters more "
    "than S-Bahn proximity alone: RE and RB headways run every 20–60 "
    "minutes, so missing the train is a bigger cost than missing a "
    "U-Bahn. For a commute out to Erkner, Potsdam, or the wider "
    "Brandenburg region, this walk is workable daily. Pair it with "
    "the S+U-Bahn tile to gauge the connection density on the local "
    "side of the trip."
)

_EMPTY_MSG = "No regional-rail (RE / RB) station within walking distance."


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
        "tier": "green", "rule": "regional-rail station within short walk",
        "numeric": "850 m to Ostkreuz",
        "features": [{"name": "Ostkreuz", "distance_m": 850}],
    })
    sys_low = msgs[0]["content"].lower()
    # Load-bearing distinction from the S+U tile: mentions RE/RB and
    # explains the headway trade-off.
    assert "re" in sys_low and "rb" in sys_low
    assert "headway" in sys_low or "headways" in sys_low
    assert "never invert" in sys_low
    print("regional_rail_reach_insight.py selfcheck OK")
