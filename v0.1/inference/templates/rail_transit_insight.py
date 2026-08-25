"""`rail_transit_insight` — plain-English gloss of the 'Rail Transit' tile
for the Newcomer lens (S-Bahn + U-Bahn only; Tram + Bus are separate tiles).

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Newcomer framing: intercity access matters more than tram frequency.
  Key anchors are Hauptbahnhof and BER airport reachability, not local
  tram schedules or stroller access.
- The first 90 days often involve airport runs (collecting family,
  returning for forgotten items) and train journeys (exploring Germany
  or Europe). S-Bahn / U-Bahn proximity is the headline.
- No invented station names. Preserve S-Bahn / U-Bahn / Tram / Bus as
  canonical modality terms.
- English only.
"""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's public-transit reachability signal for a newcomer "
    "expat arriving in the first 90 days. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout, and a shortlist of the nearest "
    "stops each with modality (S-Bahn / U-Bahn / Tram / Bus), name, and "
    "distance in metres. Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of the nearest stop and how long the walk is; "
    "(b) intercity access anchor — mention Hauptbahnhof (main rail hub) and "
    "BER airport as the key destinations newcomers care about in the first "
    "90 days: airport runs, intercity trains, and the occasional return "
    "home. S-Bahn and U-Bahn lines are the primary way to reach both; "
    "if the nearest stop is tram or bus only, flag that S-Bahn or U-Bahn "
    "will require an interchange; "
    "(c) honest note on what amber or red means for intercity travel: "
    "more connections or a longer walk to reach the network. "
    "Ground rules: "
    "1. No invented station names — use only what the payload contains. "
    "2. Preserve S-Bahn / U-Bahn / Tram / Bus as canonical modality terms. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
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
        # One-shot: red tier — no rail nearby
        {"role": "user", "content": (
            "{\n"
            "  \"tier\": \"red\", \"rule\": \"cabs or long transfers to leave the city\",\n"
            "  \"numeric\": \"\",\n"
            "  \"top\": [{\"modality\": \"Bus\", \"name\": \"Pfarrstraße\","
            " \"distance_m\": 350}]\n"
            "}"
        )},
        {"role": "assistant", "content": (
            "Only a Bus stop sits nearby — reaching Hauptbahnhof or BER airport "
            "will require at least one interchange onto S-Bahn or U-Bahn, adding "
            "15–25 minutes to any intercity journey. In the first 90 days, when "
            "airport runs and train journeys are frequent, that interchange adds "
            "up. Factor the extra transit time and a fallback cab budget into your "
            "arrival and departure planning."
        )},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": "No transit reachability data for this address."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "red", "rule": "cabs or long transfers to leave the city",
        "numeric": "",
        "features": [{"modality": "Bus", "name": "Pfarrstraße", "distance_m": 350}],
    })
    assert msgs[0]["role"] == "system"
    # System prompt mentions inversion rule
    assert "invert" in msgs[0]["content"].lower() or "never invert" in msgs[0]["content"].lower()
    # System prompt mentions Hauptbahnhof and BER (intercity framing, not tram frequency)
    assert "hauptbahnhof" in msgs[0]["content"].lower(), \
        "system must mention Hauptbahnhof as intercity anchor"
    assert "ber" in msgs[0]["content"].lower() or "airport" in msgs[0]["content"].lower(), \
        "system must mention BER airport"
    # System does NOT foreground stroller access or tram frequency
    # (no stroller mention required — that's YF framing)
    # Red exemplar must acknowledge difficulty
    exemplar_lower = msgs[2]["content"].lower()
    assert "interchange" in exemplar_lower or "transfer" in exemplar_lower or \
           "adds" in exemplar_lower, \
        "red exemplar must flag the connection overhead"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    # Final user message
    assert msgs[-1]["role"] == "user"
    print("rail_transit_insight.py selfcheck OK")
