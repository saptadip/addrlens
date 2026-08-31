"""`gesix_quiet_insight` — GESIx socioeconomic band interpreted for a
Quiet Living audience.

Same anti-ranking framing as `gesix_newcomer_insight`, retuned for a
reader who is prioritising a calm home rather than newcomer
integration:

- (a) day/night noise character of the polygon (dense mixed-use vs
      quieter monoculture);
- (b) rent-band signal (quintile 1 = highest, quintile 5 = lowest);
- (c) 'walk the block after 22:00 before signing' caveat — the
      score describes the polygon, not the flat.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.
"""
from __future__ import annotations

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret the Berlin GESIx 2022 socioeconomic band of a Planungsraum "
    "for a reader prioritising a calm, low-noise home. Frame quintiles as "
    "tradeoffs, never as rankings. Do not use the words 'better', 'worse', "
    "or 'avoid' in a ranking sense. Always mention: "
    "(a) day and night noise character of the polygon — quintile 1 areas "
    "trend residential and quieter, especially at night; quintile 5 areas "
    "trend denser, more mixed-use, with visible weekend nightlife; "
    "(b) rent-band signal — quintile 1 carries the highest rent bands in "
    "the city; quintile 5 the lowest; mid-quintiles sit in between; "
    "(c) a 'walk the block after 22:00 before signing' caveat — the score "
    "describes the polygon around the flat, not the flat itself, and "
    "night-time noise is what a quiet-living audience actually cares about. "
    "Write ONE paragraph, 70–110 words. "
    "Ground rules: "
    "1. No invented statistics — you only have quintile + rank; do not "
    "fabricate percentages, absolute numbers, or specific facility names. "
    "2. Do not use 'better', 'worse', or 'avoid' as ranking words. "
    "3. Do not editorialise about property values or use 'good' / 'bad' "
    "as verdicts. "
    "4. English only. Do not translate 'Planungsraum' or 'Kiez'. "
    "5. Never invert the meaning of the data. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(ctx: dict) -> list[dict]:
    g = ctx  # from _ctx_gesix: {plr_name, quintile_5, rang, total, lens}
    user = (
        f"Planungsraum: {g.get('plr_name', '?')}. "
        f"GESIx quintile: {g.get('quintile_5', '?')}/5. "
        f"Rank: {g.get('rang', '?')} of {g.get('total', '?')}. "
        "Audience: quiet-living reader."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        # q1 exemplar — quietest, highest-rent polygon
        {"role": "user", "content": (
            "Planungsraum: Grunewald. GESIx quintile: 1/5. "
            "Rank: 12 of 447. Audience: quiet-living reader."
        )},
        {"role": "assistant", "content": (
            "Quiet residential streets with the highest rent band in the "
            "city — evenings and weekends run at a low hum, and night-time "
            "noise sources are sparse. You'll trade convenience and price "
            "for a calm daily rhythm. Rent bands are the highest in Berlin, "
            "which sets a real ceiling on the search. Walk the block after "
            "22:00 before signing — the score describes the polygon, not "
            "the specific flat's façade or floor."
        )},
        # q5 exemplar — densest, lowest-rent polygon
        {"role": "user", "content": (
            "Planungsraum: Neukölln-Reuterkiez. GESIx quintile: 5/5. "
            "Rank: 401 of 447. Audience: quiet-living reader."
        )},
        {"role": "assistant", "content": (
            "Dense, mixed-use streets with weekend nightlife audible from "
            "residential windows until 02:00 or later — the polygon is "
            "lively rather than quiet by design. Rent bands are among the "
            "lowest in the city, which is often what draws people here in "
            "the first place. Walk the block after 22:00 before signing "
            "and ask which side of the building the flat faces — "
            "courtyard-facing units read a full band quieter."
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
    for req in ("walk the block", "rent", "22:00"):
        assert req in joined.lower(), f"missing required framing token {req!r}"
    assert m[0]["role"] == "system"
    assert "better" in m[0]["content"].lower() and "worse" in m[0]["content"].lower(), \
        "system must name the forbidden ranking words"
    assert "rent" in m[0]["content"].lower()
    assert "22:00" in m[0]["content"] or "night" in m[0]["content"].lower()
    assert "walk the block" in m[0]["content"].lower()
    assert m[1]["role"] == "user" and "Grunewald" in m[1]["content"]
    assert m[3]["role"] == "user" and "Reuterkiez" in m[3]["content"]
    assert m[-1]["role"] == "user" and "X" in m[-1]["content"]
    empty = run(None, {"quintile_5": None})
    assert "outside" in empty["insight"].lower() or "not available" in empty["insight"].lower() \
        or "no neighbourhood" in empty["insight"].lower()
    print("gesix_quiet_insight.py selfcheck OK")
