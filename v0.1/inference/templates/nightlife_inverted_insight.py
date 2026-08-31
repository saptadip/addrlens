"""`nightlife_inverted_insight` — inverse nightlife-density gloss for
the Quiet Living lens.

Uses the shared tier+features scaffold. Same OSM `nightlife` bucket
as the newcomer lens's numeric-only tile, opposite framing: fewer
venues within 300 m is greener here.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's nightlife-density signal for someone "
    "prioritising a calm home. The tile is inverted from the newcomer "
    "lens's version — fewer bars, clubs, and pubs within 300 metres is "
    "greener here, not worse. You receive: the tier (green / amber / "
    "red), the rule, the numeric readout, and a shortlist of the "
    "closest venues each with name and distance in metres. Write ONE "
    "paragraph, 70–110 words, doing three things in order: "
    "(a) plain-English readout of the count and closest venue — under "
    "3 in 300 m is genuinely quiet, 4–8 is a lively block that will "
    "carry weekend noise until 02:00, over 8 is a party street; "
    "(b) practical framing: nightlife density predicts weekend and "
    "night-time street noise more reliably than daytime traffic. "
    "Mention the type of venue if signal is present (e.g. bars vs "
    "clubs — a Späti and a Berghain-adjacent club produce very "
    "different curves); "
    "(c) honest closing sentence: for amber or red, the flat's "
    "orientation and floor matter — courtyard-facing upper floors "
    "read a full band quieter than street-facing ground-level. Never "
    "invert the tile's framing into 'good' vs 'bad'; the same block "
    "is a positive for one audience and a negative for this one. "
    "Ground rules: no invented venue names, English only. "
    "Return only the paragraph."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"amber\", \"rule\": \"4–8 nightlife venues within 300m\",\n"
    "  \"numeric\": \"6 bars / clubs / pubs within 300 m\",\n"
    "  \"top\": [\n"
    "    {\"name\":\"Späti 24\",\"distance_m\":80},\n"
    "    {\"name\":\"Bar Zentral\",\"distance_m\":160},\n"
    "    {\"name\":\"Klub Untitled\",\"distance_m\":220}\n"
    "  ]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "Six bars, clubs, or pubs sit within a 300 metre walk of the flat "
    "— a lively block that will carry weekend noise reliably from "
    "midnight to two. The mix is not uniform: a corner Späti at 80 "
    "metres is a low-grade hum, but a club at 220 metres will push "
    "voices onto the pavement at closing. For a quiet-living audience "
    "this predicts weekend and night-time noise better than any "
    "daytime traffic count. Before signing, ask which side of the "
    "building the flat faces — courtyard-facing units read a full "
    "band quieter, and upper floors help more than a triple-glazed "
    "street-facing window."
)

_EMPTY_MSG = (
    "No bars, clubs, or pubs are recorded within a 300 metre walk of "
    "this address. For a quiet-living audience this is a strong "
    "positive — weekend and night-time street noise sources cluster "
    "in nightlife strips, and this block is not on one."
)


def build_messages(ctx: dict) -> list[dict]:
    from inference.templates._insight_base import build_tier_messages
    return build_tier_messages(
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        ctx=ctx,
    )


def run(backend, ctx: dict) -> dict:
    return run_tier(
        backend, ctx,
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        empty_msg=_EMPTY_MSG,
    )


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "green", "rule": "≤ 3 nightlife venues within 300m",
        "numeric": "2 bars / clubs / pubs within 300 m",
        "features": [{"name": "Späti 24", "distance_m": 90}],
    })
    assert "invert" in msgs[0]["content"].lower() or "inverted" in msgs[0]["content"].lower()
    assert "invent" in msgs[0]["content"].lower()
    assert "Späti 24" in msgs[-1]["content"]
    print("nightlife_inverted_insight.py selfcheck OK")
