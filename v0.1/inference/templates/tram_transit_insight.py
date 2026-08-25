"""`tram_transit_insight` — plain-English gloss of the 'Tram Transit' tile
for the Newcomer lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Tram framing: local hops, daily errands, connections onto S-Bahn / U-Bahn.
- Berlin's tram network concentrates in the east and inner north; western
  districts often have no tram at all — a red tile is not automatically a
  red flag, it may just mean bus + rail cover the address instead.
- No invented stop names. Preserve S-Bahn / U-Bahn / Tram / Bus as
  canonical modality terms.
- English only.
"""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's tram reachability signal for a newcomer expat "
    "arriving in the first 90 days. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout, and a shortlist of the "
    "nearest tram stops with name and distance in metres. Write ONE "
    "paragraph, 70–110 words, doing: "
    "(a) plain-English readout of the nearest tram stop and how long the "
    "walk is; "
    "(b) local-hop framing — trams handle short daily errands and connect "
    "onto S-Bahn / U-Bahn for longer trips; mention what a nearby tram "
    "unlocks; "
    "(c) honest note on red: Berlin's tram network concentrates in the "
    "east and inner north, so a red tile in the west often means bus + "
    "rail cover the address instead, not that the neighbourhood is "
    "poorly served. "
    "Ground rules: "
    "1. No invented stop names — use only what the payload contains. "
    "2. Preserve S-Bahn / U-Bahn / Tram / Bus as canonical modality terms. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing, "
    "but do not treat red as a failure — it may reflect network geography. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
        "top":     (ctx.get("features") or [])[:6],
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        # One-shot: red tier — no tram in this part of Berlin
        {"role": "user", "content": (
            "{\n"
            "  \"tier\": \"red\", \"rule\": \"no tram within walking distance\",\n"
            "  \"numeric\": \"\",\n"
            "  \"top\": []\n"
            "}"
        )},
        {"role": "assistant", "content": (
            "No tram stop sits within a comfortable walk from this address. "
            "That is common in the western districts, where Berlin's tram "
            "network never expanded — the neighbourhood is typically served "
            "by S-Bahn or U-Bahn plus a bus network instead. Rely on those "
            "modes for daily hops and expect a longer walk or a bus hop if "
            "you specifically want to reach a tram line for a cross-city "
            "trip in the eastern half of the city."
        )},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": "No tram stop within walking distance."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "green", "rule": "tram door-to-door for daily hops",
        "numeric": "180 m to Tram Kastanienallee",
        "features": [{"name": "Kastanienallee", "distance_m": 180}],
    })
    assert msgs[0]["role"] == "system"
    assert "tram" in msgs[0]["content"].lower()
    assert "never invert" in msgs[0]["content"].lower()
    assert msgs[-1]["role"] == "user"
    print("tram_transit_insight.py selfcheck OK")
