"""`tempo30_insight` — speed-limit gloss for the Quiet Living lens.

Standalone template (not scaffold-based) — facts are aggregate
readings from `Index.tempolimit_at`: `speed_kmh`, `distance_m`,
`reason`, `time_restriction`. Absence of an exception feature is
reported as "default 50 km/h" — not "unknown".
"""
from __future__ import annotations

import json

SAMPLER = {"temp": 0.4, "top_p": 0.9, "repetition_penalty": 1.15, "max_tokens": 320}

_SYSTEM = (
    "You interpret Berlin's speed-limit signal at a specific flat's "
    "street. You receive: the tier (green / amber / red), the rule, "
    "the numeric readout, and a metadata block with speed_kmh (int or "
    "null), distance_m (metres to the nearest exception feature), "
    "reason (e.g. 'verkehrsberuhigt', 'Lärmschutz'), and "
    "time_restriction (e.g. '22:00-06:00' or null). When speed_kmh is "
    "null, no exception is nearby — the general 50 km/h default is "
    "in effect. Write ONE paragraph, 70–110 words, doing three things "
    "in order: "
    "(a) plain-English readout of the effective speed at the flat's "
    "street — Tempo 30 territory, default 50, or arterial 60+; "
    "(b) practical framing: lower speed limits reduce collision risk "
    "AND road noise (perceived loudness roughly doubles per +10 km/h "
    "at street level). When there's a time restriction, name it — the "
    "'22:00-06:00' pattern is common near schools and hospitals; "
    "(c) honest closing sentence for amber or red: default 50 is the "
    "Berlin norm, not a warning sign; > 50 km/h at the address means "
    "the street outside is a through-route, not a residential block. "
    "Ground rules: no invented statistics, no verdicts on the "
    "neighbourhood, English only except 'Tempolimit', 'verkehrsberuhigt', "
    "'Lärmschutz'. Return only the paragraph."
)


def build_messages(ctx: dict) -> list[dict]:
    facts = json.dumps({
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
        "tempolimit": {
            "speed_kmh":        ctx.get("speed_kmh"),
            "distance_m":       ctx.get("distance_m"),
            "reason":           ctx.get("reason"),
            "time_restriction": ctx.get("time_restriction"),
        },
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            "{\n"
            "  \"tier\": \"green\", \"rule\": \"speed limit ≤ 30 km/h\",\n"
            "  \"numeric\": \"30 km/h at 15 m — verkehrsberuhigt\",\n"
            "  \"tempolimit\": {\"speed_kmh\": 30, \"distance_m\": 15,\n"
            "     \"reason\": \"verkehrsberuhigt\", \"time_restriction\": null}\n"
            "}"},
        {"role": "assistant", "content":
            "The nearest street to the flat carries a Tempolimit of "
            "30 km/h — the reason on the order is 'verkehrsberuhigt', "
            "so this is a designated traffic-calmed block rather than "
            "an accident of the local geometry. Lower posted speeds "
            "cut both collision risk and the sound of the street: "
            "perceived loudness roughly doubles per additional 10 km/h "
            "at pavement level. For a quiet-living audience this is a "
            "material advantage — evenings and mornings will read as "
            "residential, not through-route. Verify on foot at rush "
            "hour before signing; posted speed and actual speed are "
            "not the same everywhere."},
        {"role": "user", "content": facts},
    ]


def run(backend, ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    return {"insight": backend.generate_from_messages(build_messages(ctx), **SAMPLER)}


if __name__ == "__main__":
    msgs = build_messages({
        "tier": "amber", "rule": "default 50 km/h",
        "numeric": "assumed 50 km/h",
        "speed_kmh": None, "distance_m": None,
        "reason": None, "time_restriction": None,
    })
    assert "Tempolimit" in msgs[0]["content"]
    assert "invent" in msgs[0]["content"].lower()
    print("tempo30_insight.py selfcheck OK")
