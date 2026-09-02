"""`airport_reach_insight` — plain-English gloss of the 'Airport reach
(BER)' tile for the Commuter lens.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Context is scalar, not a features list — the payload carries an
  `airport` object with name + straight-line `distance_m` (or km).
  Uses the noise-style standalone-template pattern rather than the
  shared `_insight_base` scaffold.
- Distance is straight-line — real door-to-gate time depends on S9 /
  RE7 timing. The prompt reinforces this so the model does not
  invent minute counts.
- English only.
"""
from __future__ import annotations

import json

SAMPLER = {
    "temp":               0.4,
    "top_p":              0.9,
    "repetition_penalty": 1.15,
    "max_tokens":         320,
}

_SYSTEM = (
    "You interpret the 'Airport reach' reading for a reader whose "
    "commute or frequent trips involve Berlin Brandenburg Airport "
    "(BER). You receive: the airport name, straight-line distance "
    "(metres or km) from the flat to the terminal, and the derived "
    "tier. Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of the straight-line distance to BER; "
    "(b) commuter framing — for anyone who flies for work or hosts "
    "arriving family often, airport reachability compounds. Closer "
    "generally means fewer late alarms and shorter departure "
    "buffers, but the practical door-to-gate time depends on the "
    "S9 / RE7 schedule, not just the crow-flight distance; "
    "(c) honest caveat — a nearby airport also carries a noise "
    "trade-off (covered by the Quiet Living lens). "
    "Ground rules: "
    "1. No invented minute counts, train schedules, or terminal "
    "details. Do not claim a specific S-Bahn / RE line reaches the "
    "airport in X minutes. "
    "2. Refer to distance as straight-line, not door-to-gate. "
    "3. English only. Preserve 'BER' as the terminal code. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    airport = ctx.get("airport") or {}
    facts = json.dumps({
        "airport": airport,
        "tier":    ctx.get("tier"),
        "numeric": ctx.get("numeric"),
    }, ensure_ascii=False, indent=2)

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"airport\": {\"name\": \"BER\", \"distance_m\": 18400},\n"
            "  \"tier\":    \"green\",\n"
            "  \"numeric\": \"18 km to BER\"\n"
            "}"},
        {"role": "assistant", "content":
            "BER sits about 18 km from the door in a straight line. "
            "For anyone flying regularly for work — or hosting arrivals — "
            "that proximity compounds over the year: shorter "
            "departure buffers, easier evening arrivals, less time on the "
            "S9 or RE7 corridor. The practical door-to-gate time depends "
            "on the train schedule and terminal transfers, not on the "
            "crow-flight distance alone, so treat this as a rough exposure "
            "signal. If flight noise matters, cross-check the Quiet "
            "Living lens tiles alongside this reading."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    airport = ctx.get("airport") or {}
    if not airport or airport.get("distance_m") is None:
        return {"insight": "No airport reference configured for this city."}
    msgs = build_messages(ctx)
    text = backend.generate_from_messages(msgs, **SAMPLER)
    return {"insight": text}


if __name__ == "__main__":
    msgs = build_messages({
        "airport": {"name": "BER", "distance_m": 18400},
        "tier":    "green",
        "numeric": "18 km to BER",
    })
    assert msgs[0]["role"] == "system"
    sys_low = msgs[0]["content"].lower()
    assert "straight-line" in sys_low
    assert "s9" in sys_low or "re7" in sys_low
    assert "never invert" in sys_low
    # Empty-airport shortcut.
    empty = run(None, {"airport": {}})
    assert "no airport" in empty["insight"].lower()
    print("airport_reach_insight.py selfcheck OK")
