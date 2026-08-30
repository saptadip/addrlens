"""`kita_insight` — plain-English gloss of the 'Kita reachability' tile.
Same per-card architecture as gesix/refuge/noise/etc."""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's Kita (daycare) reachability signal for an "
    "English-speaking expat considering a specific flat. You receive: the "
    "tier (green / amber / red), the rule text, the numeric readout, and "
    "a shortlist of the closest Kitas each with name / distance in metres / "
    "total-places capacity / operator_type (typically 'freier Träger' meaning "
    "non-profit or private, or 'Eigenbetrieb' meaning city-run) / pedagogical "
    "approach (e.g. Situationsansatz, Montessori-Pädagogik). Write ONE paragraph, "
    "70–110 words, doing: "
    "(a) plain-English readout of density in the walking bubble; "
    "(b) mix of operator types you'll be applying to (Eigenbetrieb slots are "
    "allocated centrally by Bezirk, freier Träger apply directly to each Kita — "
    "these are different application processes an expat needs to know); "
    "(c) any pedagogy pattern in the top few (a Kiez leaning heavily "
    "Waldorf-pädagogik feels different from one dominated by Situationsansatz). "
    "Close with the practical anchor: Berlin Kita capacity is under demand "
    "citywide, apply 9–12 months before the desired start date. "
    "Ground rules: no invented Kita names, no verdicts, English only "
    "except proper terminology (Kita, Träger, Situationsansatz). "
    "Return only the paragraph."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"green\", \"rule\": \"≥3 kitas within 400m\", "
    "\"numeric\": \"4 within 400m · nearest 178m\",\n"
    "  \"top\": [\n"
    "    {\"name\":\"EKT Sonnenschein\",\"distance_m\":178,"
    "\"capacity\":22,\"operator_type\":\"freier Träger\","
    "\"approach\":\"Situationsansatz\"},\n"
    "    {\"name\":\"Kindergärten NordOst · Choriner\",\"distance_m\":260,"
    "\"capacity\":75,\"operator_type\":\"Eigenbetrieb\","
    "\"approach\":\"Situationsansatz\"},\n"
    "    {\"name\":\"Waldorfkindergarten Prenzlberg\",\"distance_m\":330,"
    "\"capacity\":42,\"operator_type\":\"freier Träger\","
    "\"approach\":\"Waldorfpädagogik\"}\n"
    "  ]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "Four registered Kitas sit within a 400 metre walk of the flat, with "
    "the nearest at 178 metres — a genuinely dense reachability for "
    "Berlin. The local mix is roughly split between freier Träger "
    "(private non-profits you apply to directly) and one Eigenbetrieb "
    "(city-run, allocated centrally through your Bezirk). Pedagogy leans "
    "mostly Situationsansatz — Berlin's default child-led approach — "
    "with one Waldorfpädagogik option 330 metres away for parents "
    "wanting that route. Kita capacity in Berlin is under demand "
    "citywide; start your applications nine to twelve months before "
    "the desired start date."
)

_EMPTY_MSG = "No Kita reachability data available for this address."


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
    msgs = build_messages({"tier": "green", "rule": "x", "numeric": "y",
                            "features": [{"name": "K", "distance_m": 100,
                                           "operator_type": "freier Träger",
                                           "approach": "Situationsansatz"}]})
    assert "Kita" in msgs[0]["content"]
    assert "invented" in msgs[0]["content"].lower() or "invent" in msgs[0]["content"].lower()
    assert "K" in msgs[-1]["content"]
    print("kita_insight.py selfcheck OK")
