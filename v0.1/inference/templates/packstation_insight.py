"""`packstation_insight` — plain-English gloss of the 'Parcel pickup' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Frames Germany's parcel-logistics reality: deliveries assume the recipient
  can pick up mis-timed packages from a locker or Filiale within a few days.
- Newcomers order more parcels in the first months (furnishing an apartment,
  replacing electronics), so a distant Packstation compounds fast.
- Do NOT recommend specific carriers or Filialen beyond what the payload names,
  and do NOT promise locker availability or opening hours.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret the parcel-pickup proximity signal for a newcomer expat "
    "in Berlin in their first 90 days. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout (distance to nearest), and a "
    "shortlist of the closest DHL Packstation lockers or Deutsche Post branches "
    "each with name and distance in metres. Write ONE paragraph, 70–110 words, "
    "doing: "
    "(a) plain-English readout of how far the nearest pickup point is; "
    "(b) practical newcomer framing: Germany's parcel logistics assume the "
    "recipient can retrieve mis-timed deliveries within a few days, and newcomers "
    "order more parcels early on (furnishing, replacing electronics) so a distant "
    "pickup compounds fast — mention the nearest name if present, unless the "
    "name is a generic tag like 'parcel_locker' in which case just say 'a DHL "
    "Packstation locker'; "
    "(c) honest closing note on 'amber' or 'red': a long walk turns weekly "
    "pickups into a chore, and missed pickup deadlines mean returned parcels. "
    "Ground rules: "
    "1. No invented locker numbers, opening hours, or capacity claims. "
    "2. Do not promise specific carrier coverage beyond what is named. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"red\", \"rule\": \"no parcel pickup point nearby — expect long detours\",\n"
    "  \"numeric\": \"\",\n"
    "  \"top\": []\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "No DHL Packstation locker or Deutsche Post branch appears within a "
    "comfortable walk of this address. That matters more than it sounds: "
    "in the first months a newcomer typically orders more parcels than "
    "usual — furnishing a flat, replacing electronics that do not fit "
    "German plugs — and a distant pickup turns each delivery into a "
    "chore. Missed pickup deadlines mean returned parcels, which cost "
    "another shipment cycle. Plan a route that fits into an existing "
    "commute rather than a dedicated errand."
)

_EMPTY_MSG = (
    "No parcel pickup point found nearby. Germany's parcel logistics "
    "assume you can retrieve mis-timed deliveries within a few days, and "
    "newcomers order more parcels early on. A distant pickup turns each "
    "delivery into a chore; plan a route that fits into an existing commute."
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
        "tier": "red", "rule": "no parcel pickup point nearby — expect long detours",
        "numeric": "", "features": [],
    })
    assert msgs[0]["role"] == "system"
    assert "never invert" in msgs[0]["content"].lower()
    assert "packstation" in msgs[0]["content"].lower() or "parcel" in msgs[0]["content"].lower(), \
        "system prompt must name the parcel-logistics context"
    exemplar_lower = msgs[2]["content"].lower()
    assert "chore" in exemplar_lower or "detour" in exemplar_lower or "commute" in exemplar_lower, \
        "red exemplar must acknowledge the friction"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    assert msgs[-1]["role"] == "user"
    print("packstation_insight.py selfcheck OK")
