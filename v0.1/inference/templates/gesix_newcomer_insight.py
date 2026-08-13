"""`gesix_newcomer_insight` — GESIx socioeconomic band interpreted for a newcomer expat.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Per Spec E: frame quintiles as tradeoffs, never as rankings.
- Forbidden ranking words: "better", "worse", "avoid" in a ranking sense.
- Three mandatory content elements in the exemplar and final output:
  (a) likely language mix on the block,
  (b) rent-band signal,
  (c) a "walk the block before signing" caveat.
- Two one-shot exemplars: q1 (quietest, highest-rent) and q5 (densest,
  lowest-rent) to show the tradeoff framing across the full range.
- No GESIx acronym in user-facing prose — describe the signal, not the name.
- No invented statistics beyond quintile + rank.
"""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret the Berlin GESIx 2022 socioeconomic band of a Planungsraum "
    "for a newcomer expat. Frame quintiles as tradeoffs, never as rankings. "
    "Do not use the words 'better', 'worse', or 'avoid' in a ranking sense. "
    "Always mention: "
    "(a) likely language mix on the block — quintile 1 areas trend monolingual "
    "German; quintile 5 areas trend multilingual with visible English, Turkish, "
    "or Arabic presence; "
    "(b) rent-band signal — quintile 1 carries the highest rent bands in the "
    "city; quintile 5 the lowest; mid-quintiles sit in between; "
    "(c) a 'walk the block before signing' caveat — the score describes the "
    "polygon around the flat, not the flat itself. "
    "Write ONE paragraph, 70–110 words. "
    "Ground rules: "
    "1. No invented statistics — you only have quintile + rank; do not fabricate "
    "percentages, absolute numbers, or specific facility names. "
    "2. Do not use 'better', 'worse', or 'avoid' as ranking words. "
    "3. Do not editorialise about property values or use 'good' / 'bad' as "
    "verdicts. "
    "4. English only. Do not translate 'Planungsraum' or 'Kita'. "
    "5. Never invert the meaning of the data. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    g = ctx  # from _ctx_gesix: {plr_name, quintile_5, rang, total, lens}
    user = (
        f"Planungsraum: {g.get('plr_name', '?')}. "
        f"GESIx quintile: {g.get('quintile_5', '?')}/5. "
        f"Rank: {g.get('rang', '?')} of {g.get('total', '?')}. "
        "Audience: newcomer expat, first 90 days."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        # One-shot q1 exemplar — quietest, highest-rent quintile
        {"role": "user", "content": (
            "Planungsraum: Grunewald. GESIx quintile: 1/5. "
            "Rank: 12 of 447. Audience: newcomer expat."
        )},
        {"role": "assistant", "content": (
            "Quiet, monolingual-German streets with the highest rent band in the "
            "city — you'll trade language immersion for a calmer routine. Expect "
            "fewer international grocers within walking distance. Walk the block "
            "on a weekday evening before signing so you know how the neighbourhood "
            "feels off business hours."
        )},
        # One-shot q5 exemplar — densest, lowest-rent quintile
        {"role": "user", "content": (
            "Planungsraum: Neukölln-Reuterkiez. GESIx quintile: 5/5. "
            "Rank: 401 of 447. Audience: newcomer expat."
        )},
        {"role": "assistant", "content": (
            "Dense, multilingual streets with cheaper rent bands and a mixed "
            "international presence — you'll pick up services in English or "
            "Turkish easily. Nightlife runs late and the block is busy. Walk "
            "the block after 22:00 before signing so you know whether the "
            "noise matches your rhythm."
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
    # Anti-ranking assertion: no ranking words in exemplars
    m = build_messages({"plr_name": "X", "quintile_5": 1, "rang": 10, "total": 447})
    joined = "\n".join(x["content"] for x in m if x["role"] == "assistant")
    for word in ("better", "worse", "avoid"):
        assert word not in joined.lower(), f"ranking word {word!r} leaked into exemplar"
    # Required framing tokens must appear across the two exemplars
    for req in ("walk the block", "rent", "language"):
        assert req in joined.lower(), f"missing required framing token {req!r}"
    # System prompt assertions
    assert m[0]["role"] == "system"
    assert "better" in m[0]["content"].lower() and "worse" in m[0]["content"].lower(), \
        "system must name the forbidden ranking words"
    assert "rent" in m[0]["content"].lower(), "system must mention rent-band signal"
    assert "language" in m[0]["content"].lower(), "system must mention language mix"
    assert "walk the block" in m[0]["content"].lower(), "system must include walk-the-block caveat"
    # Both one-shot turns present (positions 1+2 = q1, 3+4 = q5)
    assert m[1]["role"] == "user" and "Grunewald" in m[1]["content"]
    assert m[2]["role"] == "assistant"
    assert m[3]["role"] == "user" and "Reuterkiez" in m[3]["content"]
    assert m[4]["role"] == "assistant"
    # Final user message
    assert m[-1]["role"] == "user" and "X" in m[-1]["content"]
    # Empty-input shortcut
    empty = run(None, {"quintile_5": None})
    assert "outside" in empty["insight"].lower() or "not available" in empty["insight"].lower() \
        or "no neighbourhood" in empty["insight"].lower()
    print("gesix_newcomer_insight.py selfcheck OK")
