"""`library_insight` — plain-English gloss of the 'Public library' tile.

Response schema: { "insight": "<one paragraph, 70–110 words>" }.

Design notes
------------
- Frames the library as a low-friction 'third place' for newcomers:
  free Wi-Fi, warm study space, English fiction shelf, integration events,
  no purchase pressure and no German-only barrier to entering.
- Distance-to-nearest is the driver; short walks turn library use into a
  habit, long walks turn it into a chore.
- Do NOT overpromise specific English-language collections or events beyond
  what the payload names.
- English only.
"""
from __future__ import annotations

from inference.templates._insight_base import DEFAULT_SAMPLER, run_tier

SAMPLER = DEFAULT_SAMPLER

_SYSTEM = (
    "You interpret the public-library proximity signal for a newcomer expat "
    "in Berlin in their first 90 days. You receive: the tier (green / amber / "
    "red), the rule text, the numeric readout (distance to nearest), and a "
    "shortlist of the closest libraries each with name and distance in metres. "
    "Write ONE paragraph, 70–110 words, doing: "
    "(a) plain-English readout of how far the nearest library is; "
    "(b) practical newcomer framing: the library is one of the lowest-friction "
    "'third places' available before a newcomer has a job or a Verein — free "
    "Wi-Fi, warm study space, English fiction shelf, integration events, no "
    "purchase pressure, no German-only barrier to enter — mention the nearest "
    "name if present; "
    "(c) honest closing note on 'amber' or 'red': the further the library, the "
    "more library use becomes a planned trip rather than a spontaneous stop. "
    "Ground rules: "
    "1. No invented statistics, event names, or collection sizes beyond the payload. "
    "2. Do not promise English-language books or events at specific branches. "
    "3. English only. "
    "4. Never invert the meaning of a red tier into positive framing. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)

_EXEMPLAR_USER = (
    "{\n"
    "  \"tier\": \"red\", \"rule\": \"no public library nearby\",\n"
    "  \"numeric\": \"\",\n"
    "  \"top\": []\n"
    "}"
)

_EXEMPLAR_ASSISTANT = (
    "No public library shows within a comfortable walk of this address. "
    "That matters more than it looks: in the early months, before a job "
    "or a Verein anchors your week, the library is one of the few warm, "
    "quiet, purchase-free places open to a newcomer with no German. A "
    "longer walk turns it from a spontaneous stop into a planned trip, "
    "so it drops out of your routine. Check whether any branch is a "
    "short transit ride and treat the visit as a weekly habit rather "
    "than an errand."
)

_EMPTY_MSG = (
    "No public library found nearby. In the early months before a job "
    "or a Verein anchors your week, the library is a low-friction third "
    "place — free Wi-Fi, warm study space, no purchase pressure. Check "
    "whether any branch is a short transit ride and plan a weekly visit."
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
        "tier": "red", "rule": "no public library nearby",
        "numeric": "", "features": [],
    })
    assert msgs[0]["role"] == "system"
    assert "never invert" in msgs[0]["content"].lower()
    # System prompt names the "third place" framing
    assert "third place" in msgs[0]["content"].lower() or "wi-fi" in msgs[0]["content"].lower(), \
        "system prompt must frame the library as a third place"
    exemplar_lower = msgs[2]["content"].lower()
    assert "walk" in exemplar_lower or "transit" in exemplar_lower, \
        "red exemplar must acknowledge the distance friction"
    assert "great" not in exemplar_lower and "excellent" not in exemplar_lower, \
        "red exemplar must not positively invert"
    assert msgs[-1]["role"] == "user"
    print("library_insight.py selfcheck OK")
