"""`gesix_commuter_insight` — GESIx socioeconomic band interpreted for
a Commuter audience.

Same anti-ranking framing as the other gesix_* templates, retuned for
a reader who is prioritising a fast, reliable daily commute:

- (a) the transit-density character of the polygon — quintile 1
      polygons often sit further from the S/U network, quintile 5
      polygons often sit ON it;
- (b) the daily rhythm framing (peak-hour crowding vs empty
      platforms), not the quintile-as-verdict;
- (c) the 'ride the actual line one weekday morning' caveat — the
      polygon score is not a substitute for the peak-time experience.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.
"""
from __future__ import annotations

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret the Berlin GESIx 2022 socioeconomic band of a Planungsraum "
    "for a reader prioritising a fast, reliable daily commute. Frame "
    "quintiles as tradeoffs, never as rankings. Do not use the words "
    "'better', 'worse', or 'avoid' in a ranking sense. Always mention: "
    "(a) the transit-density character of the polygon — quintile 1 "
    "polygons often sit further from the S / U network (the tradeoff for "
    "residential quiet), quintile 5 polygons often sit on it (the tradeoff "
    "for daily density); "
    "(b) the daily-rhythm framing — a station ON the doorstep means peak-"
    "hour platform crowding and boarding delays; a station a longer walk "
    "away often means an emptier platform but a longer daily walk. Both "
    "shape the commute in different ways; "
    "(c) a 'ride the actual line one weekday morning before signing' "
    "caveat — the polygon score is not a substitute for the peak-time "
    "experience of the specific S/U line the commute will use. "
    "Write ONE paragraph, 70–110 words. "
    "Ground rules: "
    "1. No invented statistics — you only have quintile + rank; do not "
    "fabricate percentages, absolute numbers, or specific line letters. "
    "2. Do not use 'better', 'worse', or 'avoid' as ranking words. "
    "3. Do not editorialise about property values or use 'good' / 'bad' "
    "as verdicts. "
    "4. English only. Do not translate 'Planungsraum' or 'Kiez'. "
    "5. Never invert the meaning of the data. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    g = ctx
    user = (
        f"Planungsraum: {g.get('plr_name', '?')}. "
        f"GESIx quintile: {g.get('quintile_5', '?')}/5. "
        f"Rank: {g.get('rang', '?')} of {g.get('total', '?')}. "
        "Audience: daily-commute reader."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        # q1 exemplar — outer, quieter, further from the network
        {"role": "user", "content": (
            "Planungsraum: Grunewald. GESIx quintile: 1/5. "
            "Rank: 12 of 447. Audience: daily-commute reader."
        )},
        {"role": "assistant", "content": (
            "A quiet outer polygon that sits further from the dense "
            "S / U network — the tradeoff is a longer daily walk to a "
            "station in exchange for calmer residential streets at "
            "each end of the day. Peak-hour platforms tend to run "
            "less crowded here than in central polygons, so boarding "
            "is easier, but the compounded walk over a working week "
            "is real. Ride the actual line one weekday morning before "
            "signing — the polygon score is not a substitute for the "
            "peak-time experience of the specific line the commute uses."
        )},
        # q5 exemplar — dense, transit-on-doorstep polygon
        {"role": "user", "content": (
            "Planungsraum: Neukölln-Reuterkiez. GESIx quintile: 5/5. "
            "Rank: 401 of 447. Audience: daily-commute reader."
        )},
        {"role": "assistant", "content": (
            "A dense, mixed-use polygon that typically sits on the "
            "S / U network — the daily walk is short, but peak-hour "
            "platform crowding and boarding delays are the tradeoff. "
            "Rush-hour compression compounds over a week of round-"
            "trips, so the commute character shifts from walking time "
            "to waiting time. Ride the actual line one weekday morning "
            "before signing to see whether the platform density suits "
            "you — the polygon score describes the neighbourhood, not "
            "the specific line."
        )},
        {"role": "user", "content": user},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if ctx.get("quintile_5") is None:
        return {"insight": (
            "No neighbourhood profile available for this address "
            "(outside the Senate's GESIx polygons)."
        )}
    msgs = build_messages(ctx)
    text = backend.generate_from_messages(msgs, **SAMPLER)
    return {"insight": text}


if __name__ == "__main__":
    m = build_messages({"plr_name": "X", "quintile_5": 1, "rang": 10, "total": 447})
    joined = "\n".join(x["content"] for x in m if x["role"] == "assistant")
    for word in ("better", "worse", "avoid"):
        assert word not in joined.lower(), f"ranking word {word!r} leaked into exemplar"
    for req in ("ride the actual line", "peak", "polygon score"):
        assert req in joined.lower(), f"missing required framing token {req!r}"
    assert m[0]["role"] == "system"
    assert "better" in m[0]["content"].lower() and "worse" in m[0]["content"].lower(), \
        "system must name the forbidden ranking words"
    assert "commute" in m[0]["content"].lower()
    assert "ride the actual line" in m[0]["content"].lower()
    assert m[1]["role"] == "user" and "Grunewald" in m[1]["content"]
    assert m[3]["role"] == "user" and "Reuterkiez" in m[3]["content"]
    assert m[-1]["role"] == "user" and "X" in m[-1]["content"]
    empty = run(None, {"quintile_5": None})
    assert "outside" in empty["insight"].lower() or "no neighbourhood" in empty["insight"].lower()
    print("gesix_commuter_insight.py selfcheck OK")
