"""`transit_insight` — 'Transit stop within walk' tile gloss."""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret Berlin's public-transit reachability signal. You receive: "
    "tier / rule / numeric plus a shortlist of the nearest stop per modality "
    "(each row has modality = S-Bahn / U-Bahn / Tram / Bus, name, "
    "distance_m, walk_min). Write ONE paragraph, 70–110 words: "
    "(a) shortest walk-minute across all four modes as the headline; "
    "(b) modal balance — an address with U-Bahn plus tram plus bus within "
    "10 minutes has very different daily options from one with only bus at "
    "12 minutes. Name the specific nearest station where present; "
    "(c) practical anchor for a young family: stroller access matters — "
    "modern S-Bahn and U-Bahn stations have lifts but many older tram / bus "
    "stops don't, and Berlin U-Bahn lift outage rates are non-trivial. "
    "No invented station names. English only, preserve S-Bahn / U-Bahn / "
    "Tram / Bus as canonical. Return the paragraph only."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\":\"green\",\"rule\":\"≥1 stop within 5 min stroller walk\",\n"
    "  \"top\":[{\"modality\":\"U-Bahn\",\"name\":\"U Eberswalder Str.\","
    "\"walk_min\":2},{\"modality\":\"Tram\",\"name\":\"M1 -> Stadt\","
    "\"walk_min\":3},{\"modality\":\"Bus\",\"name\":\"Sredzkistraße\","
    "\"walk_min\":4},{\"modality\":\"S-Bahn\",\"name\":\"S+U Schönhauser Allee\","
    "\"walk_min\":9}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "The nearest stop is U-Bahn Eberswalder Str., a two-minute walk — "
    "genuinely at your door for daily use. A Tram (M1) and a Bus stop "
    "sit within four minutes, and the closest S-Bahn (S+U Schönhauser "
    "Allee) is nine. Four modes within a ten-minute walk gives real "
    "flexibility: the U-Bahn and S-Bahn will have lifts for stroller "
    "access, though check current outages before you commit — Berlin "
    "U-Bahn lift downtime is a well-known daily annoyance. The tram "
    "and bus stops here are useful but street-level, so factor in kerb "
    "ramps and the odd broken pavement."
)

_EMPTY_MSG = "No transit reachability data for this address."


def build_messages(ctx: dict) -> list[dict]:
    from inference.templates._insight_base import build_tier_messages
    return build_tier_messages(
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        ctx=ctx,
        top_k=6,
    )


def run(backend, ctx: dict) -> dict:
    return run_tier(
        backend, ctx,
        system=_SYSTEM,
        exemplar_user=_EXEMPLAR_USER,
        exemplar_assistant=_EXEMPLAR_ASSISTANT,
        empty_msg=_EMPTY_MSG,
        top_k=6,
    )


if __name__ == "__main__":
    msgs = build_messages({"features": [{"modality": "U-Bahn", "name": "X", "walk_min": 3}]})
    assert "U-Bahn" in msgs[0]["content"]
    assert "invent" in msgs[0]["content"].lower()
    print("transit_insight.py selfcheck OK")
