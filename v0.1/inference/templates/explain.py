"""`explain` template — sentiment-neutral card explainer.
Verbatim system + few-shot from phase3/server.py:explain_card.

Response schema (§7.3.2): { "explanation": "<two-or-three-sentence text>" }.
"""
from __future__ import annotations

import json

# Sampler tuned lower than impression — factual, not creative.
SAMPLER = {
    "temp": 0.55,
    "top_p": 0.9,
    "repetition_penalty": 1.2,
    "max_tokens": 180,
}


def build_messages(card_type: str, fields: dict) -> list[dict]:
    facts = json.dumps(fields, ensure_ascii=False, indent=2)[:1500]
    return [
        {"role": "system", "content":
            "You explain a Berlin neighborhood data card to an English-speaking family who is new to Germany. "
            "Translate every German administrative term inline in parentheses on first use, e.g. "
            "'freier Träger (a non-profit or private provider)'. Two to three short sentences, under 70 words. "
            "Speak to them as \"you\". Do NOT invent facts not present in the data. No lists, no headings."},
        {"role": "user", "content":
            "Data:\n"
            "{\"count\": 32, \"sample\": {\"name\":\"Kita Sonnenschein\",\"t_art\":\"freier Träger\","
            "\"ang_1\":\"Situationsansatz\",\"e_platz\":\"65\"}}"},
        {"role": "assistant", "content":
            "You have 32 registered Kitas (daycares) within a 10-minute walk. The nearby Kita Sonnenschein "
            "is run by a freier Träger (a non-profit or private provider — the alternative is Eigenbetrieb, "
            "city-run). It uses the Situationsansatz approach, a Berlin pedagogy where activities emerge "
            "from the children's own experiences rather than a fixed curriculum, and has 65 total places."},
        {"role": "user", "content":
            f"Data:\n{facts}"},
    ]


def run(backend, context: dict) -> dict:
    card_type = (context.get("card_type") or "").strip()[:40]
    fields    = context.get("fields") or {}
    if not card_type or not fields:
        raise ValueError("card_type and fields required")
    msgs = build_messages(card_type, fields)
    text = backend.generate_from_messages(msgs, **SAMPLER)
    return {"explanation": text}


if __name__ == "__main__":
    # Prompt is well-formed for a synthetic Kita.
    msgs = build_messages("edu-kita",
                          {"name": "Kita Test", "t_art": "freier Träger", "e_platz": "42"})
    assert msgs[0]["role"] == "system"
    assert "Kita Test" in msgs[-1]["content"]
    assert "42" in msgs[-1]["content"]
    print("explain.py selfcheck OK")
