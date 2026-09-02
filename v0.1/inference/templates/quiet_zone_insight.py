"""`quiet_zone_insight` — Berlin 'Ruhige Gebiete' (§47d BImSchG)
nearest-zone gloss for the Quiet Living lens.

Uses the shared tier+features scaffold. The facts JSON carries the
nearest quiet-zone anchor as the single top-item (name / distance /
lat / lon); the system prompt frames the reading around habit-forming
proximity rather than one-off visits.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's 'Ruhige Gebiete' (§47d BImSchG designated "
    "quiet-recreation zones) reachability for someone considering a "
    "specific flat and prioritising a calm home. You receive: the tier "
    "(green / amber / red), the rule text, the numeric readout, and a "
    "shortlist of the closest quiet-zone anchors each with name, "
    "distance in metres, and (when available) size in hectares. Write "
    "ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of the walk to the nearest quiet zone — "
    "under 400 metres is doorstep-close, 400–1000 m is a habit-forming "
    "stroll, further is a planned trip; "
    "(b) practical framing for a quiet-living audience: 'Ruhige Gebiete' "
    "are legally designated, not just green space — they are meant to "
    "protect quiet, and their edges matter for daily walks; "
    "(c) honest closing note when the tier is amber or red: the further "
    "the zone, the less it anchors your week's noise recovery. If the "
    "tier is red, note the important caveat that state forests "
    "(Grunewald, Tegeler Forst, Köpenicker Wald) and other "
    "Landschaftsschutzgebiete are NOT on the §47d list — they are "
    "protected under Forstwirtschaft law instead — so an address next "
    "to a big forest can still read red on this tile despite objectively "
    "abundant nearby quiet. "
    "Ground rules: no invented park names, no verdicts, English only "
    "except proper terminology ('Ruhige Gebiete'). "
    "Return only the paragraph."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"quiet zone within 400 m\",\n"
    "  \"numeric\": \"320 m to Volkspark Friedrichshain\",\n"
    "  \"top\": [\n"
    "    {\"name\":\"Volkspark Friedrichshain\",\"distance_m\":320,\n"
    "     \"lat\":52.528,\"lon\":13.435}\n"
    "  ]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "The nearest designated quiet zone, Volkspark Friedrichshain, sits "
    "320 metres from your door — a genuine doorstep escape when the "
    "street outside starts to grate. 'Ruhige Gebiete' are protected by "
    "the Federal Immission Control Act, so the designation carries more "
    "than tourist-guide weight: these are places Berlin specifically "
    "keeps quiet. At this distance the park becomes a daily anchor for "
    "evening walks and weekend lie-ins, not a planned trip. Verify the "
    "route on foot — the last block matters as much as the total."
)

_EMPTY_MSG = (
    "No 'Ruhige Gebiete' quiet zone was returned within the search "
    "radius. Berlin's protected quiet zones are concentrated in a "
    "handful of larger inner-city parks; further out, weekly recovery "
    "walks will need a transit ride or a bike trip. Note the caveat: "
    "state forests (Grunewald, Tegeler Forst, Köpenicker Wald) and "
    "other Landschaftsschutzgebiete are NOT on the §47d list — they "
    "are protected under Forstwirtschaft law instead — so an address "
    "next to a big forest can read empty here despite abundant nearby "
    "quiet."
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
        "tier": "green", "rule": "quiet zone within 400 m",
        "numeric": "300 m to Test-Park",
        "features": [{"name": "Test-Park", "distance_m": 300,
                      "lat": 52.5, "lon": 13.4}],
    })
    assert "Ruhige Gebiete" in msgs[0]["content"]
    assert "Test-Park" in msgs[-1]["content"]
    assert "invent" in msgs[0]["content"].lower()
    # State-forest exclusion caveat is load-bearing — Grunewald / Tegeler
    # Forst adjacencies read RED on this tile because they're protected
    # under Forstwirtschaft law rather than §47d BImSchG. The system
    # prompt must name that gap so the AI paragraph can flag it when the
    # tier is red. Strict presence — a future edit that drops "Grunewald"
    # in favour of a vaguer "state forest" (or vice versa) must fail so
    # the concrete example survives.
    sys_low = msgs[0]["content"].lower()
    assert "grunewald" in sys_low, \
        "system must name Grunewald as the concrete state-forest example"
    assert "forstwirtschaft" in sys_low, \
        "system must name the alternative protection mechanism (Forstwirtschaft)"
    assert "landschaftsschutz" in sys_low, \
        "system must name Landschaftsschutzgebiete as the broader excluded set"
    # And the empty-msg for state-forest-adjacent addresses hits the
    # empty-features shortcut; it must carry the same caveat.
    assert "grunewald" in _EMPTY_MSG.lower(), \
        "empty-msg must acknowledge the state-forest exclusion"
    print("quiet_zone_insight.py selfcheck OK")
