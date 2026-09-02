"""`commuter_rail_transit_insight` — plain-English gloss of the
'S+U-Bahn reach' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Commuter framing: the S / U station near home is where the workday
  starts and ends twice a day, five days a week. Reliability + walk
  time matter more than intercity access (the Newcomer lens covers
  Hauptbahnhof / BER framing).
- The line letters the payload carries (e.g. `directions: ["Alexanderplatz","Warschauer Str."]`
  or the platform base "S Ostkreuz") are the anchor — the model may
  reference them but must not invent new lines or stations.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's S-Bahn and U-Bahn reachability signal for a "
    "reader who commutes daily. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout, and a shortlist of the "
    "nearest S / U stops each with modality (S-Bahn / U-Bahn), name, "
    "distance in metres and (when present) a `directions` list of terminal "
    "or through-station names. Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of the nearest S / U station and how long "
    "the walk is; "
    "(b) commuter framing — this is the daily start of the workday, "
    "twice per day, five days per week; a short reliable walk to "
    "S-Bahn or U-Bahn is worth several hours per week vs. a bus "
    "interchange. If both S and U are present, note the network "
    "redundancy — one line down doesn't strand you; "
    "(c) honest note on what amber or red means for a daily commute: "
    "a longer walk twice a day compounds, and single-mode coverage "
    "adds risk on delays. "
    "Ground rules: "
    "1. No invented station names, line letters, or terminals — use "
    "only what the payload contains. "
    "2. Preserve S-Bahn / U-Bahn as canonical modality terms. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "5. Do not foreground airports or intercity main stations — this "
    "tile is about the daily commute, not intercity trips. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"S + U within 5 min walk\",\n"
    "  \"numeric\": \"S 220 m · U 380 m\",\n"
    "  \"top\": ["
    "{\"modality\": \"S-Bahn\", \"name\": \"S Ostkreuz\", \"distance_m\": 220,"
    " \"directions\": [\"Warschauer Str.\", \"Ostbahnhof\"]},"
    "{\"modality\": \"U-Bahn\", \"name\": \"U Frankfurter Tor\", \"distance_m\": 380}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "S Ostkreuz sits about 220 metres from the door — roughly a "
    "three-minute walk — with U Frankfurter Tor a further block away "
    "at 380 metres. That's genuine network redundancy for the daily "
    "commute: an S-Bahn disruption toward Warschauer Str. or "
    "Ostbahnhof leaves the U-Bahn as a backup, so a delay doesn't "
    "strand you. Twice a day, five days a week, the short reliable "
    "walk compounds into hours saved per month versus a bus "
    "interchange. Pair this with the tram or bus tile for the "
    "last-mile options once you're home."
)

_EMPTY_MSG = "No S-Bahn or U-Bahn station within walking distance."


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
        "tier": "green", "rule": "S + U within 5 min walk",
        "numeric": "S 220 m · U 380 m",
        "features": [
            {"modality": "S-Bahn", "name": "S Ostkreuz", "distance_m": 220,
             "directions": ["Warschauer Str.", "Ostbahnhof"]},
            {"modality": "U-Bahn", "name": "U Frankfurter Tor", "distance_m": 380},
        ],
    })
    assert msgs[0]["role"] == "system"
    sys_low = msgs[0]["content"].lower()
    # Commuter framing is load-bearing — the Newcomer rail tile mentions
    # Hauptbahnhof + BER; this one must NOT.
    assert "hauptbahnhof" not in sys_low, \
        "commuter rail tile must not foreground intercity anchors"
    assert "ber airport" not in sys_low and "brandenburg" not in sys_low, \
        "commuter rail tile must not mention BER airport"
    assert "daily" in sys_low and "commute" in sys_low, \
        "system must foreground the daily-commute framing"
    assert "never invert" in sys_low
    assert msgs[-1]["role"] == "user"
    print("commuter_rail_transit_insight.py selfcheck OK")
