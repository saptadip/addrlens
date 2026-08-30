"""`supermarket_insight` — 'Supermarket within walk' tile gloss."""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

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

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\":\"green\",\"rule\":\"≥1 supermarket within 5 min walk\",\n"
    "  \"top\":[{\"name\":\"REWE\",\"walk_min\":3,\"brand\":\"REWE\"},"
    "{\"name\":\"EDEKA\",\"walk_min\":6,\"brand\":\"EDEKA\"},"
    "{\"name\":\"LIDL\",\"walk_min\":7,\"brand\":\"LIDL\"},"
    "{\"name\":\"Bio Company\",\"walk_min\":8,\"brand\":\"Bio Company\",\"organic\":true}]\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "The nearest supermarket is a REWE at a three-minute walk, with "
    "four options in total inside an eight-minute stroller bubble. "
    "The local mix is well-rounded: two full-range stores (REWE, "
    "EDEKA), one discount (LIDL), and one organic (Bio Company) — "
    "you won't be forced into a single brand's price band. The "
    "organic option is a genuine plus if that matters to your weekly "
    "shop. Remember German supermarkets shut on Sundays under the "
    "Ladenschlussgesetz, so verify each store's Saturday closing time "
    "before relying on one for the big weekly shop."
)

_EMPTY_MSG = "No supermarket reachability data for this address."


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
    msgs = build_messages({"features": [{"name": "S", "walk_min": 4}]})
    assert "supermarket" in msgs[0]["content"].lower()
    assert "invent" in msgs[0]["content"].lower()
    print("supermarket_insight.py selfcheck OK")
