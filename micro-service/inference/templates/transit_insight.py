"""`transit_insight` — 'Transit stop within walk' tile gloss."""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

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


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier": ctx.get("tier"), "rule": ctx.get("rule"), "numeric": ctx.get("numeric"),
        "top": (ctx.get("features") or [])[:6],
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"tier\":\"green\",\"rule\":\"≥1 stop within 5 min stroller walk\",\n"
            "  \"top\":[{\"modality\":\"U-Bahn\",\"name\":\"U Eberswalder Str.\","
            "\"walk_min\":2},{\"modality\":\"Tram\",\"name\":\"M1 -> Stadt\","
            "\"walk_min\":3},{\"modality\":\"Bus\",\"name\":\"Sredzkistraße\","
            "\"walk_min\":4},{\"modality\":\"S-Bahn\",\"name\":\"S+U Schönhauser Allee\","
            "\"walk_min\":9}]\n"
            "}"},
        {"role": "assistant", "content":
            "The nearest stop is U-Bahn Eberswalder Str., a two-minute walk — "
            "genuinely at your door for daily use. A Tram (M1) and a Bus stop "
            "sit within four minutes, and the closest S-Bahn (S+U Schönhauser "
            "Allee) is nine. Four modes within a ten-minute walk gives real "
            "flexibility: the U-Bahn and S-Bahn will have lifts for stroller "
            "access, though check current outages before you commit — Berlin "
            "U-Bahn lift downtime is a well-known daily annoyance. The tram "
            "and bus stops here are useful but street-level, so factor in kerb "
            "ramps and the odd broken pavement."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": "No transit reachability data for this address."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({"features": [{"modality": "U-Bahn", "name": "X", "walk_min": 3}]})
    assert "U-Bahn" in msgs[0]["content"]
    assert "invent" in msgs[0]["content"].lower()
    print("transit_insight.py selfcheck OK")
