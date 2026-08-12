"""`playground_insight` — 'Playground within stroller walk' tile gloss."""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's stroller-walk playground reachability signal. "
    "You receive: tier / rule / numeric plus a shortlist of the closest "
    "playgrounds with name, distance in metres, and optional area in m² and "
    "renovated_year. Write ONE paragraph, 70–110 words: "
    "(a) plain-English density readout (how many within the walk bubble, distance "
    "to nearest); "
    "(b) if any area_m2 values are present, mention the size range — a small "
    "500 m² pocket playground is a very different daily experience from a "
    "5000 m² neighbourhood park; "
    "(c) if renovated_year values appear, flag whether the near playgrounds are "
    "recently renewed (post-2018) or older equipment. "
    "Close with the practical anchor: age-suitability of equipment can only be "
    "confirmed in person — the dataset lists locations, not what's actually "
    "installed. "
    "No invented names or years. English only. Return the paragraph only."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier": ctx.get("tier"), "rule": ctx.get("rule"), "numeric": ctx.get("numeric"),
        "top": (ctx.get("features") or [])[:5],
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"tier\":\"green\",\"rule\":\"≥1 playground within 400m\","
            "\"numeric\":\"3 within 400m · nearest 165m\",\n"
            "  \"top\":[{\"name\":\"Oderberger Str. 19\",\"distance_m\":165,"
            "\"area_m2\":3599,\"renovated_year\":2012},"
            "{\"name\":\"Choriner Str. 47\",\"distance_m\":230,"
            "\"area_m2\":1120,\"renovated_year\":2020},"
            "{\"name\":\"Kolmarer Str.\",\"distance_m\":380,"
            "\"area_m2\":720}]\n"
            "}"},
        {"role": "assistant", "content":
            "Three registered playgrounds sit within a 400 metre stroller walk, "
            "the nearest at 165 metres. Their sizes vary from a modest 720 m² "
            "pocket to a substantial 3,599 m² neighbourhood site, so daily "
            "options span both quick-visit and stay-a-while formats. One of the "
            "three was renovated in 2020, another in 2012 — the mix is "
            "reasonable but not uniformly recent. What's actually installed "
            "(age-suitability, shade, fencing, condition) only reveals itself "
            "on a walk-through — the city dataset locates the sites but does "
            "not describe the equipment inside them."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": "No playground reachability data for this address."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({"tier": "green", "features": [{"name": "P", "distance_m": 100}]})
    assert "playground" in msgs[0]["content"].lower()
    assert "invent" in msgs[0]["content"].lower() or "fabricat" in msgs[0]["content"].lower()
    print("playground_insight.py selfcheck OK")
