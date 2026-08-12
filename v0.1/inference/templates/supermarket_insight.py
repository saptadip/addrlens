"""`supermarket_insight` — 'Supermarket within walk' tile gloss."""
from __future__ import annotations
import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's supermarket reachability signal for an "
    "English-speaking expat. Data is OSM-only (Berlin publishes no BOD "
    "supermarket layer). You receive: tier / rule / numeric plus a "
    "shortlist of the nearest supermarkets (name, distance_m, walk_min, "
    "optional brand, opening_hours, wheelchair, organic). Write ONE "
    "paragraph, 70–110 words: "
    "(a) plain-English density readout (nearest walk minutes, count in the "
    "5-minute bubble); "
    "(b) brand mix — Berlin brands split roughly into full-range "
    "(Rewe, Edeka, Kaufland), discount (Lidl, Aldi, Netto, Penny) and "
    "organic (Bio Company, Alnatura, Denns); note the local balance; "
    "(c) any organic tag hits, or the absence of any organic option in the "
    "top few. "
    "Close with the practical anchor: Berlin supermarkets close on Sundays "
    "under Ladenschlussgesetz — verify Saturday opening hours before you "
    "rely on a specific store for the weekly big shop. "
    "No invented brands or hours. English only, preserve German brand "
    "names verbatim. Return the paragraph only."
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
            "  \"tier\":\"green\",\"rule\":\"≥1 supermarket within 5 min walk\",\n"
            "  \"top\":[{\"name\":\"REWE\",\"walk_min\":3,\"brand\":\"REWE\"},"
            "{\"name\":\"EDEKA\",\"walk_min\":6,\"brand\":\"EDEKA\"},"
            "{\"name\":\"LIDL\",\"walk_min\":7,\"brand\":\"LIDL\"},"
            "{\"name\":\"Bio Company\",\"walk_min\":8,\"brand\":\"Bio Company\",\"organic\":true}]\n"
            "}"},
        {"role": "assistant", "content":
            "The nearest supermarket is a REWE at a three-minute walk, with "
            "four options in total inside an eight-minute stroller bubble. "
            "The local mix is well-rounded: two full-range stores (REWE, "
            "EDEKA), one discount (LIDL), and one organic (Bio Company) — "
            "you won't be forced into a single brand's price band. The "
            "organic option is a genuine plus if that matters to your weekly "
            "shop. Remember German supermarkets shut on Sundays under the "
            "Ladenschlussgesetz, so verify each store's Saturday closing time "
            "before relying on one for the big weekly shop."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": "No supermarket reachability data for this address."}
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({"features": [{"name": "S", "walk_min": 4}]})
    assert "supermarket" in msgs[0]["content"].lower()
    assert "invent" in msgs[0]["content"].lower()
    print("supermarket_insight.py selfcheck OK")
