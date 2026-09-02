"""`commuter_tram_transit_insight` — plain-English gloss of the
'Tram reach' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Commuter framing: trams are the daily last-mile from home to the
  nearest S / U hub, or the intra-district route for east-Berlin
  addresses where the tram network is denser than the U-Bahn.
- No invented stop names. Preserve S-Bahn / U-Bahn / Tram / Bus.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's tram reachability signal for a reader who "
    "commutes daily. You receive: the tier (green / amber / red), the "
    "rule text, the numeric readout, and a shortlist of the nearest "
    "tram stops with name and distance in metres. Write ONE paragraph, "
    "70–110 words, doing: "
    "(a) plain-English readout of the nearest tram stop and how long "
    "the walk is; "
    "(b) commuter framing — trams handle the daily last-mile between "
    "home and the nearest S / U hub, and in east-Berlin districts they "
    "are often the fastest intra-district route where the U-Bahn "
    "coverage thins. Trams also run predictably in winter when snow "
    "slows buses; "
    "(c) honest note on amber or red — a further walk to any tram is "
    "workable if S-Bahn or U-Bahn is close, but real friction on a "
    "daily commute if the rail tile is also weak. "
    "Ground rules: "
    "1. No invented stop names — use only what the payload contains. "
    "2. Preserve S-Bahn / U-Bahn / Tram / Bus as canonical modality terms. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"tram at the doorstep\",\n"
    "  \"numeric\": \"180 m to Tram Bersarinplatz\",\n"
    "  \"top\": [{\"name\": \"Bersarinplatz\", \"distance_m\": 180}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "A tram stop sits about 180 metres from the door at Bersarinplatz "
    "— roughly a two-minute walk. For a daily commute that's a "
    "reliable last-mile: trams run to a predictable schedule and hold "
    "up well in winter when snow slows buses. Pair it with the "
    "S-Bahn / U-Bahn tile to see how far a single ride reaches on the "
    "way to work, and remember that in east-Berlin districts the tram "
    "network often outruns U-Bahn coverage for intra-district hops."
)

_EMPTY_MSG = "No tram stop within walking distance."


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
        "tier": "green", "rule": "tram at the doorstep",
        "numeric": "180 m to Tram Bersarinplatz",
        "features": [{"name": "Bersarinplatz", "distance_m": 180}],
    })
    sys_low = msgs[0]["content"].lower()
    assert "tram" in sys_low and "daily" in sys_low and "commute" in sys_low
    assert "never invert" in sys_low
    print("commuter_tram_transit_insight.py selfcheck OK")
