"""`pediatrician_insight` — 'Pediatrician within walk' tile gloss."""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's paediatric-doctor reachability signal for an "
    "English-speaking expat. Data source is OpenStreetMap community tags "
    "so inner-district coverage is reliable but outer districts may "
    "under-report. You receive: tier / rule / numeric plus a shortlist of "
    "the nearest paediatric practices (name, distance, optional address, "
    "phone, website, opening hours, wheelchair). Write ONE paragraph, "
    "70–110 words: "
    "(a) plain-English density readout (how many within the walk bubble); "
    "(b) mention the OSM caveat honestly — coverage improves in central "
    "Berlin, thins toward the edges; "
    "(c) practical anchor for German paediatric care: paediatricians (called "
    "Kinderarzt/Kinderärztin here) can be scarce with statutory insurance "
    "(GKV) — call ahead to confirm they accept new patients, and check "
    "whether the practice has step-free access if you'll be visiting "
    "regularly with a stroller. "
    "No invented names or numbers. English only, but preserve Kinderarzt as "
    "the local term. Return the paragraph only."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\":\"green\",\"rule\":\"≥1 paediatric within 800m\","
    "\"numeric\":\"2 within 800m · nearest 539m (Dr. Euler)\",\n"
    "  \"top\":[{\"name\":\"Dr. Euler\",\"distance_m\":539,"
    "\"address\":\"Schönhauser Allee 82\",\"phone\":\"+49 30 4488900\","
    "\"wheelchair\":true},"
    "{\"name\":\"Kinderarztpraxis Hubermann & Kollegen\",\"distance_m\":720,"
    "\"address\":\"Kastanienallee 27\"}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "Two paediatric practices sit within an 800 metre walk of the "
    "flat, the nearest at 539 metres. Coverage here is OSM "
    "community-tagged, so central-Berlin reads like this tend to be "
    "reliable — outer districts frequently under-report. As a family "
    "moving in, remember that a Kinderarzt with statutory insurance "
    "(GKV) can be hard to sign up with new patients: phone both "
    "practices to confirm they're accepting before you commit, and "
    "note that only one of these two is flagged step-free — helpful "
    "if you'll be arriving weekly with a stroller."
)

_EMPTY_MSG = "No paediatric practice data available for this address."


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
    msgs = build_messages({"features": [{"name": "P", "distance_m": 500}]})
    assert "OpenStreetMap" in msgs[0]["content"]
    assert "invent" in msgs[0]["content"].lower()
    print("pediatrician_insight.py selfcheck OK")
