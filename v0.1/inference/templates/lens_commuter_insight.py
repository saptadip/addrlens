"""`lens_commuter_insight` — one-call lens-level executive summary for the
Commuter lens.

Consumes ALL 9 Commuter tile scoring outputs at once and returns a strict-
JSON response the SPA renders as the "AI Insight" panel above the Commuter
tile grid. Replaces per-tile `Get Insight` buttons (one call per tile,
one Cloudflare hop per tile) with a single fan-in call per lens.

Response schema:

    {
      "executive_summary": "<2-3 sentences of plain-English framing>",
      "sections": [
        {"title": "Rail & regional",
         "tiles": ["commuter_rail_transit", "regional_rail_reach"],
         "verdict": "green|amber|red|unknown",
         "note": "<1 sentence>"},
        ...
      ],
      "highlights_green": [{"tile": "commuter_rail_transit",
                            "one_line": "U-Bahn 240 m from the door"}, ...],
      "highlights_red":   [{"tile": "airport_reach",
                            "one_line": "BER is 32 km away"}, ...],
      "fit_score": 0-100 or omitted
    }

Design notes
------------
- Sections are HARDCODED in `LENS_SECTION_MAP`, not LLM-chosen. The LLM
  only fills `verdict` (rolled up over the section's tiles — worst wins),
  `note` (one sentence), and the highlight `one_line` fields.
- Unlike `lens_newcomer_insight`, this template does NOT dynamically
  import sibling per-tile `*_insight.py` templates for framing — those
  are being deleted as part of the Qwen retirement (Route B). The
  summariser relies only on the tile payload's `label` / `rule` /
  `numeric` / `caveat` fields passed by the caller.
- Verdict rollup is deterministic: after the LLM responds, `run()`
  overwrites the `verdict` field on each section from the input tile
  tiers (`red > amber > green > unknown` — worst wins). Model can't
  accidentally promote red → green.
- No invention. System forbids citing facts absent from the payload.
- No info-only tiles in Commuter — every tile emits real green / amber
  / red / unknown. `info` is still accepted in `_TIER_RANK` as an alias
  for `unknown` for parity with `lens_newcomer_insight`.
"""
from __future__ import annotations

import json

# Lower temp than tile insights — this is structured JSON output, not
# flowing prose. max_tokens fits 5 sections + up to 6 highlights on a
# 9-tile lens without truncation.
SAMPLER = {
    "temp":               0.35,
    "top_p":              0.9,
    "repetition_penalty": 1.1,
    "max_tokens":         1400,
}

# Commuter lens tile groupings. Keys must match `LensTileConfig.key` in
# `app/cities/berlin.py::COMMUTER_LENS`. Every tile must appear in
# exactly one section — the __main__ selfcheck enforces this.
LENS_SECTION_MAP: list[dict] = [
    {"title": "Rail & regional",
     "tiles": ["commuter_rail_transit", "regional_rail_reach"]},
    {"title": "Short-hop transit",
     "tiles": ["commuter_tram_transit", "commuter_bus_transit"]},
    {"title": "Cycling & car",
     "tiles": ["cycling_network", "car_sharing_reach", "ev_charging_reach"]},
    {"title": "Long-haul travel",
     "tiles": ["airport_reach"]},
    {"title": "Neighbourhood profile",
     "tiles": ["gesix_commuter"]},
]

# Worst-tier-wins ordering. The scoring pipeline emits `green`, `amber`,
# `red`, and `unknown` only (see `app/core/scoring/constants.py`).
# `info` is accepted as an alias for `unknown` for parity with
# `lens_newcomer_insight` — Commuter has no info-only tiles today (all
# 9 tiles emit real tiers, including `airport_reach` which uses km-based
# thresholds and `gesix_commuter` which uses socioeconomic quintiles).
# The `.get(tier, -1)` default excludes any non-ranked value from the
# rollup so a section of only unknown tiles rolls up to `unknown`.
_TIER_RANK = {"green": 0, "amber": 1, "red": 2, "unknown": -1}

# Fit score weights — used by `_compute_fit_score` after section rollup.
# green=100 (close/direct/dense), amber=60 (walkable but not doorstep —
# full middle of the range), red=20 (not zero because "no rail within
# 900 m" still means SOME transit is reachable further). Unknown
# sections are excluded from both numerator and denominator so they
# don't drag the score toward zero.
_FIT_WEIGHTS = {"green": 100, "amber": 60, "red": 20}


def _compute_fit_score(sections: list) -> int | None:
    """Weighted average of section verdicts. Returns None when no
    tiered section exists (all-unknown case) so the frontend can hide
    the score chip instead of showing 0."""
    total, n = 0, 0
    for sec in sections or []:
        w = _FIT_WEIGHTS.get(sec.get("verdict"))
        if w is None:
            continue
        total += w
        n += 1
    if not n:
        return None
    return round(total / n)


def _rollup_verdict(tiles: list[dict]) -> str:
    """Worst-tier-wins over a section's tiles. Ignores unknown / info /
    missing tiers. Returns 'unknown' if no tiered tile in the section."""
    ranked = [_TIER_RANK.get(t.get("tier", ""), -1) for t in tiles]
    real = [r for r in ranked if r >= 0]
    if not real:
        return "unknown"
    worst = max(real)
    for name, rank in _TIER_RANK.items():
        if rank == worst:
            return name
    return "unknown"


_SYSTEM = (
    "You are writing a per-lens executive summary for the Commuter lens "
    "of a Berlin address-intelligence tool. The user commutes daily and "
    "cares about door-to-transit time, cycling network reach, and "
    "multi-modal options (S+U-Bahn, tram, bus, regional rail, cycling, "
    "car-sharing, EV charging, airport reach). Not a family-specific or "
    "first-90-days audience. You receive a JSON payload with: (a) the "
    "address's Bezirk / Ortsteil hint, (b) a list of 9 Commuter tile "
    "results, each carrying `key`, `label`, `tier` (green / amber / red "
    "/ unknown), `rule`, `numeric`, and `caveat`. "
    "Return ONE JSON object with EXACTLY these top-level keys: "
    "`executive_summary` (string, 2-3 sentences), "
    "`sections` (array — see below), "
    "`highlights_green` (array of {tile, one_line}), "
    "`highlights_red` (array of {tile, one_line}). "
    "Rules for `executive_summary`: 2-3 sentences of plain English, "
    "60-100 words total. Frame the address as a daily-commute prospect. "
    "Cite the strongest 1-2 positives and the sharpest 1-2 concerns "
    "drawn from tiered tiles (green / amber / red). All 9 Commuter "
    "tiles carry real tiers — every tile is eligible to be cited as a "
    "positive or concern. "
    "IMPORTANT — section names vs tile names: `expected_sections[].title` "
    "values (e.g., 'Rail & regional', 'Short-hop transit', 'Cycling & "
    "car', 'Long-haul travel', 'Neighbourhood profile') are GROUPINGS "
    "for the `sections` field ONLY. They MUST NOT appear in the "
    "executive summary paragraph. In the summary, refer to each signal "
    "by its real-world function using the tile `label` (e.g., 'S+U-Bahn "
    "reach', 'tram reach', 'cycling network', 'car-sharing'), NOT the "
    "section title that contains it. Writing 'The Rail & regional is "
    "strong' is WRONG — that conflates a section grouping with a "
    "specific tile. Write 'S+U-Bahn is 240 m away' instead. "
    "No German words except proper names (Bezirk, Ortsteil, S-Bahn, "
    "U-Bahn, Straßenbahn, Kiez are fine as terminology). "
    "Rules for `sections`: return EXACTLY the sections listed in the "
    "payload's `expected_sections` array, in the same order, with the "
    "same `title` and `tiles` values. Fill only the `verdict` field "
    "(one of green / amber / red / unknown — worst tile in the section "
    "wins) and the `note` field (one sentence explaining what pulls "
    "the verdict). Do NOT invent new sections. Do NOT rename sections. "
    "Do NOT reassign tiles between sections. "
    "Rules for `highlights_green` and `highlights_red`: rank the tiles "
    "by signal strength — pick UP TO 3 green tiles that stand out and "
    "UP TO 3 red or amber tiles that stand out. Each `one_line` is a "
    "short factual claim grounded in the tile's `rule` / `numeric` — "
    "never invent numbers. Omit `highlights_red` entirely if no tile "
    "is amber or red. Omit `highlights_green` entirely if no tile is "
    "green. Never put the same tile in both lists. "
    "Ground rules: "
    "(1) Only cite facts present in the payload. Never invent counts, "
    "distances, times, or names. "
    "(2) Never promote a red or amber tile to green in `sections` or "
    "in the summary. "
    "(3) Do not editorialise about 'good' or 'bad' neighbourhoods. "
    "Describe, don't judge. "
    "(4) TONE DISCIPLINE per tier: green = clearly positive framing "
    "('close', 'direct', 'dense', 'on your doorstep'). amber = neutral, "
    "situational framing ('walkable but not doorstep', 'a short walk', "
    "'~12-minute walk', 'reachable', 'a short ride'). red = clearly "
    "negative framing ('far', 'no ... nearby', 'plan a longer commute', "
    "'lacks'). Do NOT use red-tier language ('far', 'lacks') for amber "
    "tiles — amber is the middle ground, not a failure. An S-Bahn "
    "900 m away is amber ('a 12-minute walk' or 'a short bike ride'), "
    "NOT 'far'. Reserve strong negative framing for tiles the payload "
    "actually marks red. "
    "(5) Return ONLY the JSON object. No preamble, no code fences, no "
    "trailing prose."
)


def _build_tile_payload(tile_contexts: list[dict]) -> list[dict]:
    """Trim each tile_context to the fields the summariser needs. Drops
    `features`, `sources`, `legend`, `framing` — the summariser reads
    only the verdict axis and the tile's rule/numeric/caveat, not the
    tile drill-down or a framing excerpt (this template does NOT use
    the `_load_tile_framings` dynamic-import pattern from
    `lens_newcomer_insight` because the per-tile `*_insight.py`
    templates are being deleted in the Qwen-retirement cleanup)."""
    out = []
    for tc in tile_contexts or []:
        if not isinstance(tc, dict):
            continue
        key = tc.get("key")
        if not key:
            continue
        out.append({
            "key":     key,
            "label":   tc.get("label", key),
            "tier":    tc.get("tier"),
            "rule":    tc.get("rule"),
            "numeric": tc.get("numeric"),
            "caveat":  tc.get("caveat"),
        })
    return out


def build_messages(context: dict) -> list[dict]:
    """Assemble the 4-message list: system, exemplar user, exemplar
    assistant (valid JSON), real user facts.

    Expected `context` shape:
      {
        "address_hint": {"bezirk": "...", "ortsteil": "..."},
        "tile_contexts": [
          {"key": "commuter_rail_transit", "label": "S+U-Bahn reach",
           "tier": "green", "rule": "S-Bahn ≤500 m OR U-Bahn ≤500 m",
           "numeric": "U-Bahn 240 m · S-Bahn 620 m",
           "caveat": None},
          ...
        ],
      }
    """
    if not isinstance(context, dict):
        raise ValueError("context must be an object")

    hint = context.get("address_hint") or {}
    tiles = _build_tile_payload(context.get("tile_contexts") or [])

    facts = {
        "address_hint": {
            "bezirk":   hint.get("bezirk", ""),
            "ortsteil": hint.get("ortsteil", ""),
        },
        "expected_sections": LENS_SECTION_MAP,
        "tiles": tiles,
    }
    facts_json = json.dumps(facts, ensure_ascii=False, indent=2)

    # Compact one-shot exemplar. Genericised placeholders — a real
    # bezirk / ortsteil in the exemplar was being copied into the
    # response by smaller models, corrupting the address hint.
    exemplar_user = json.dumps({
        "address_hint": {"bezirk": "<Bezirk from payload>",
                          "ortsteil": "<Ortsteil from payload>"},
        "expected_sections": LENS_SECTION_MAP,
        "tiles": "<9 Commuter tiles with key/tier/rule/numeric/caveat>",
    }, ensure_ascii=False)

    exemplar_assistant = json.dumps({
        "executive_summary": (
            "This Ortsteil reads strong on the Commuter axes that matter "
            "most day to day: S+U-Bahn is a 3-minute walk, cycling "
            "infrastructure is on the block, and car-sharing is dense. "
            "The main gap is airport reach — BER is 32 km away, so a "
            "monthly airport trip needs the S9 or a longer taxi ride. "
            "Regional rail is a reachable 1.6 km if long-haul travel "
            "matters."
        ),
        "sections": [
            {"title": "Rail & regional",
             "tiles": ["commuter_rail_transit", "regional_rail_reach"],
             "verdict": "amber",
             "note": "S+U-Bahn on your doorstep; regional rail is 1.6 km — a short bike ride."},
            {"title": "Short-hop transit",
             "tiles": ["commuter_tram_transit", "commuter_bus_transit"],
             "verdict": "green",
             "note": "Tram 220 m and bus 140 m — both on the block."},
            {"title": "Cycling & car",
             "tiles": ["cycling_network", "car_sharing_reach", "ev_charging_reach"],
             "verdict": "green",
             "note": "Cycleway on the doorstep, 4 car-sharing points and 3 EV chargers within 500 m."},
            {"title": "Long-haul travel",
             "tiles": ["airport_reach"],
             "verdict": "amber",
             "note": "BER is 32 km — a 45-minute S9 ride or a longer taxi."},
            {"title": "Neighbourhood profile",
             "tiles": ["gesix_commuter"],
             "verdict": "green",
             "note": "GESIx Q2 — stable socioeconomic band for a commuter household."},
        ],
        "highlights_green": [
            {"tile": "commuter_rail_transit",
             "one_line": "U-Bahn 240 m and S-Bahn 620 m from the door."},
            {"tile": "commuter_bus_transit",
             "one_line": "Nearest bus stop 140 m — one-minute walk."},
            {"tile": "car_sharing_reach",
             "one_line": "4 car-sharing points within 500 m."},
        ],
        "highlights_red": [
            {"tile": "airport_reach",
             "one_line": "BER is 32 km — plan a monthly S9 or taxi for long-haul travel."},
            {"tile": "regional_rail_reach",
             "one_line": "Nearest RE/RB platform 1.6 km — a short bike ride."},
        ],
    }, ensure_ascii=False)

    return [
        {"role": "system",    "content": _SYSTEM},
        {"role": "user",      "content": exemplar_user},
        {"role": "assistant", "content": exemplar_assistant},
        {"role": "user",      "content": facts_json},
    ]


def _validate_shape(obj: dict) -> None:
    """Strict shape check on the model output. Raises ValueError with a
    specific reason so `run()` can surface it (or retry once with a
    stricter re-prompt). Deliberately narrow — the LLM should be fixing
    its own output, not the caller."""
    if not isinstance(obj, dict):
        raise ValueError("response is not a JSON object")
    if not isinstance(obj.get("executive_summary"), str):
        raise ValueError("executive_summary must be a string")
    sections = obj.get("sections")
    if not isinstance(sections, list) or len(sections) != len(LENS_SECTION_MAP):
        raise ValueError(
            f"sections must be an array of length {len(LENS_SECTION_MAP)}"
        )
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            raise ValueError(f"sections[{i}] is not an object")
        expected = LENS_SECTION_MAP[i]
        if sec.get("title") != expected["title"]:
            raise ValueError(
                f"sections[{i}].title drifted from '{expected['title']}'"
            )
        if list(sec.get("tiles") or []) != list(expected["tiles"]):
            raise ValueError(
                f"sections[{i}].tiles drifted from expected list"
            )
        if not isinstance(sec.get("note"), str):
            raise ValueError(f"sections[{i}].note must be a string")
    for key in ("highlights_green", "highlights_red"):
        if key in obj:
            arr = obj[key]
            if not isinstance(arr, list):
                raise ValueError(f"{key} must be an array")
            for j, h in enumerate(arr):
                if not isinstance(h, dict):
                    raise ValueError(f"{key}[{j}] is not an object")
                if not isinstance(h.get("tile"), str) or not h["tile"]:
                    raise ValueError(f"{key}[{j}].tile must be a non-empty string")
                if not isinstance(h.get("one_line"), str) or not h["one_line"]:
                    raise ValueError(f"{key}[{j}].one_line must be a non-empty string")


def _apply_deterministic_rollup(obj: dict, tile_contexts: list[dict]) -> dict:
    """Deterministic post-processing on the LLM output.

    (1) Overwrite each section's `verdict` with the rollup computed from
        input tile tiers — model can't accidentally promote red → green.
    (2) Filter `highlights_green` so only tiles with actual `tier="green"`
        survive; drop any highlight whose tile key isn't in the input.
    (3) Filter `highlights_red` so only tiles with `tier="amber"` or
        `tier="red"` survive; drop unknown / green / info tiles.
    (4) Deduplicate: if the same tile lands in both green and red lists
        (LLM confusion), keep the green entry and drop from red.
    (5) Compute `fit_score` from the rolled-up section verdicts.

    The LLM has to guess the verdict from prose, but we own the tier
    data — so trust the data, not the guess."""
    by_key = {tc.get("key"): tc for tc in (tile_contexts or [])
              if isinstance(tc, dict) and tc.get("key")}

    for sec in obj.get("sections") or []:
        sec_tiles = [by_key.get(k) for k in (sec.get("tiles") or [])]
        sec_tiles = [t for t in sec_tiles if t is not None]
        sec["verdict"] = _rollup_verdict(sec_tiles)

    def _filter_hi(arr, allowed_tiers: set) -> list:
        keep = []
        for h in arr or []:
            if not isinstance(h, dict):
                continue
            key = h.get("tile")
            tile = by_key.get(key)
            if tile is None:
                continue
            if tile.get("tier") not in allowed_tiers:
                continue
            keep.append(h)
        return keep

    if "highlights_green" in obj:
        obj["highlights_green"] = _filter_hi(obj["highlights_green"], {"green"})
    if "highlights_red" in obj:
        obj["highlights_red"] = _filter_hi(obj["highlights_red"], {"amber", "red"})

    if obj.get("highlights_green") and obj.get("highlights_red"):
        green_keys = {h.get("tile") for h in obj["highlights_green"]}
        obj["highlights_red"] = [h for h in obj["highlights_red"]
                                 if h.get("tile") not in green_keys]

    _score = _compute_fit_score(obj.get("sections") or [])
    if _score is not None:
        obj["fit_score"] = _score

    return obj


def run(backend, context: dict) -> dict:
    """Call the backend, parse + validate JSON, apply deterministic
    verdict rollup, return `{"lens_insight": <obj>}`. Malformed JSON or
    schema drift → one retry with the same prompt (LLMs often self-
    correct on the second sample). Second failure → raise ValueError so
    the caller can fall back to a degraded text-only summary."""
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    tile_contexts = context.get("tile_contexts") or []
    if not tile_contexts:
        return {"lens_insight": {
            "executive_summary":
                "No tile scoring available for this address yet.",
            "sections": [
                {"title": s["title"], "tiles": s["tiles"],
                 "verdict": "unknown", "note": "No data."}
                for s in LENS_SECTION_MAP
            ],
        }}
    msgs = build_messages(context)

    last_err = None
    for attempt in range(2):
        text = backend.generate_from_messages(msgs, **SAMPLER)
        try:
            obj = json.loads(text)
            _validate_shape(obj)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            continue
        obj = _apply_deterministic_rollup(obj, tile_contexts)
        return {"lens_insight": obj}
    raise ValueError(
        f"lens_commuter_insight: model returned invalid JSON twice "
        f"({type(last_err).__name__}: {last_err})"
    )


if __name__ == "__main__":
    # -- LENS_SECTION_MAP covers all 9 Commuter tile keys, no orphans,
    # no duplicates. If a new Commuter tile lands in berlin.py without
    # a section entry, this assert fails at boot.
    _commuter_tile_keys = {
        "commuter_rail_transit", "commuter_tram_transit", "commuter_bus_transit",
        "regional_rail_reach", "cycling_network", "car_sharing_reach",
        "ev_charging_reach", "airport_reach", "gesix_commuter",
    }
    _mapped = []
    for sec in LENS_SECTION_MAP:
        _mapped.extend(sec["tiles"])
    assert set(_mapped) == _commuter_tile_keys, \
        f"LENS_SECTION_MAP diverges from Commuter tile keys — " \
        f"missing: {_commuter_tile_keys - set(_mapped)}, " \
        f"extra: {set(_mapped) - _commuter_tile_keys}"
    assert len(_mapped) == len(set(_mapped)), \
        "LENS_SECTION_MAP has a tile in more than one section"

    # -- Deterministic verdict rollup: worst-wins over green/amber/red,
    # unknown ignored; empty section → unknown.
    assert _rollup_verdict([]) == "unknown"
    assert _rollup_verdict([{"tier": "unknown"}]) == "unknown"
    assert _rollup_verdict([{"tier": "green"}]) == "green"
    assert _rollup_verdict([{"tier": "green"}, {"tier": "amber"}]) == "amber"
    assert _rollup_verdict([{"tier": "amber"}, {"tier": "red"}]) == "red"
    assert _rollup_verdict([{"tier": "green"}, {"tier": "unknown"}]) == "green"
    assert _rollup_verdict([{"tier": "info"}]) == "unknown"

    # -- build_messages: 4-role sequence, JSON-parsable exemplars, real
    # user carries the address_hint and the full tile list.
    _ctx = {
        "address_hint": {"bezirk": "Pankow", "ortsteil": "Prenzlauer Berg"},
        "tile_contexts": [
            {"key": "commuter_rail_transit", "label": "S+U-Bahn reach",
             "tier": "green", "rule": "S-Bahn ≤500 m OR U-Bahn ≤500 m",
             "numeric": "U-Bahn 240 m"},
            {"key": "airport_reach", "label": "Airport reach (BER)",
             "tier": "red", "rule": "≤20 km green",
             "numeric": "32 km"},
        ],
    }
    msgs = build_messages(_ctx)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"], \
        [m["role"] for m in msgs]
    # System prompt names the four JSON keys and the anti-invention /
    # anti-inversion rules — load-bearing constraints; a future edit
    # that drops them silently degrades output quality.
    _sys = msgs[0]["content"]
    for _key in ("executive_summary", "sections", "highlights_green", "highlights_red"):
        assert _key in _sys, f"system prompt missing schema key: {_key}"
    assert "Never invent" in _sys or "never invent" in _sys.lower(), \
        "system must forbid invention"
    assert "Never promote" in _sys or "never promote" in _sys.lower(), \
        "system must forbid tier promotion (anti-inversion)"
    assert "no code fences" in _sys.lower() or "no preamble" in _sys.lower(), \
        "system must forbid markdown wrapper prose"
    # Tone-discipline rule — amber must not be described in red-tier
    # language. Anti-drift guard for the load-bearing calibration.
    assert "tone discipline" in _sys.lower(), \
        "system must carry per-tier tone discipline rule"
    assert "amber" in _sys.lower() and "middle ground" in _sys.lower(), \
        "system must explicitly frame amber as the middle ground"
    # Anti-drift: section titles are groupings for the `sections` field
    # only — they must never appear as terms in the executive summary
    # paragraph.
    assert "section names vs tile names" in _sys.lower(), \
        "system must forbid section titles in the summary paragraph"
    # Exemplar assistant must be valid JSON matching the schema.
    _ex_asst = json.loads(msgs[2]["content"])
    assert isinstance(_ex_asst["executive_summary"], str)
    assert len(_ex_asst["sections"]) == len(LENS_SECTION_MAP)
    for i, sec in enumerate(_ex_asst["sections"]):
        assert sec["title"] == LENS_SECTION_MAP[i]["title"], \
            f"exemplar section[{i}] title drifted"
        assert list(sec["tiles"]) == list(LENS_SECTION_MAP[i]["tiles"]), \
            f"exemplar section[{i}] tiles drifted"
        assert sec["verdict"] in ("green", "amber", "red", "unknown"), \
            f"exemplar section[{i}] verdict invalid: {sec.get('verdict')}"
    # Real user carries the address hint and the tile list.
    _real_user = msgs[-1]["content"]
    assert "Pankow" in _real_user
    assert "Prenzlauer Berg" in _real_user
    assert "airport_reach" in _real_user
    assert '"expected_sections"' in _real_user, \
        "real user payload must include expected_sections (shape lock)"

    # -- _validate_shape happy path + failure modes.
    _good = json.loads(msgs[2]["content"])
    _validate_shape(_good)                        # no raise

    # Bad: sections drift on title
    _bad_title = json.loads(msgs[2]["content"])
    _bad_title["sections"][0]["title"] = "Something else"
    try:
        _validate_shape(_bad_title)
    except ValueError as e:
        assert "title drifted" in str(e)
    else:
        raise AssertionError("expected ValueError on section title drift")

    # Bad: sections drift on tile list
    _bad_tiles = json.loads(msgs[2]["content"])
    _bad_tiles["sections"][0]["tiles"] = ["something_else"]
    try:
        _validate_shape(_bad_tiles)
    except ValueError as e:
        assert "tiles drifted" in str(e)
    else:
        raise AssertionError("expected ValueError on section tile drift")

    # Bad: wrong number of sections
    _bad_len = json.loads(msgs[2]["content"])
    _bad_len["sections"] = _bad_len["sections"][:2]
    try:
        _validate_shape(_bad_len)
    except ValueError as e:
        assert "length" in str(e)
    else:
        raise AssertionError("expected ValueError on wrong sections length")

    # Bad: missing executive_summary
    _bad_exec = json.loads(msgs[2]["content"])
    _bad_exec.pop("executive_summary")
    try:
        _validate_shape(_bad_exec)
    except ValueError as e:
        assert "executive_summary" in str(e)
    else:
        raise AssertionError("expected ValueError on missing executive_summary")

    # Bad: highlight missing tile field
    _bad_hi = json.loads(msgs[2]["content"])
    _bad_hi["highlights_green"][0].pop("tile")
    try:
        _validate_shape(_bad_hi)
    except ValueError as e:
        assert "tile" in str(e)
    else:
        raise AssertionError("expected ValueError on bad highlight shape")

    # -- _apply_deterministic_rollup overrides model verdict with the
    # rollup computed from tile_contexts — the source of truth is the
    # scoring pipeline, not the LLM's guess.
    _obj = {"sections": [
        {"title": "T1", "tiles": ["a", "b"], "verdict": "green", "note": "..."},
    ]}
    _tcs = [{"key": "a", "tier": "green"}, {"key": "b", "tier": "red"}]
    _obj2 = _apply_deterministic_rollup(_obj, _tcs)
    assert _obj2["sections"][0]["verdict"] == "red", \
        f"rollup should have promoted section to red, got {_obj2['sections'][0]['verdict']!r}"

    # -- Highlight tone filter: green list must contain only tiles whose
    # actual tier is green; amber tiles land in the red list; drops any
    # tile that isn't in the input at all; dedups tiles that appear in
    # both lists (green wins).
    _obj3 = {
        "highlights_green": [
            {"tile": "a", "one_line": "genuinely green"},
            {"tile": "b", "one_line": "amber wrongly claimed as green — drop"},
            {"tile": "ghost", "one_line": "not in input — drop"},
        ],
        "highlights_red": [
            {"tile": "b", "one_line": "amber correctly in red list — keep"},
            {"tile": "c", "one_line": "red correctly in red list — keep"},
            {"tile": "a", "one_line": "green wrongly in red — dedup drop"},
            {"tile": "d", "one_line": "unknown tier — drop"},
        ],
    }
    _tcs2 = [
        {"key": "a", "tier": "green"},
        {"key": "b", "tier": "amber"},
        {"key": "c", "tier": "red"},
        {"key": "d", "tier": "unknown"},
    ]
    _obj3b = _apply_deterministic_rollup(_obj3, _tcs2)
    _g_keys = [h["tile"] for h in _obj3b.get("highlights_green", [])]
    _r_keys = [h["tile"] for h in _obj3b.get("highlights_red", [])]
    assert _g_keys == ["a"], f"green list should keep only 'a', got {_g_keys}"
    assert _r_keys == ["b", "c"], f"red list should be [b, c], got {_r_keys}"

    # -- Fit score: weighted average over tiered sections; None when
    # all sections are unknown (no chip shown by frontend).
    assert _compute_fit_score([]) is None
    assert _compute_fit_score([{"verdict": "unknown"}]) is None
    assert _compute_fit_score([{"verdict": "green"}]) == 100
    assert _compute_fit_score([{"verdict": "red"}]) == 20
    assert _compute_fit_score([{"verdict": "green"}, {"verdict": "red"}]) == 60
    # Realistic Commuter scenario matching the exemplar rollup:
    # amber, green, green, amber, green → (60+100+100+60+100)/5 = 84.
    _commuter = [{"verdict": "amber"}, {"verdict": "green"},
                 {"verdict": "green"}, {"verdict": "amber"},
                 {"verdict": "green"}]
    assert _compute_fit_score(_commuter) == 84, _compute_fit_score(_commuter)
    # Rollup output carries the score post-computation.
    _obj4 = {"sections": [
        {"title": "T1", "tiles": ["a"], "verdict": "wrong", "note": "..."},
        {"title": "T2", "tiles": ["b"], "verdict": "wrong", "note": "..."},
    ]}
    _tcs4 = [{"key": "a", "tier": "green"}, {"key": "b", "tier": "red"}]
    _obj4b = _apply_deterministic_rollup(_obj4, _tcs4)
    assert _obj4b.get("fit_score") == 60, _obj4b.get("fit_score")
    # All-unknown → no fit_score field.
    _obj5 = {"sections": [{"title": "T", "tiles": ["a"], "verdict": "x", "note": "n"}]}
    _obj5b = _apply_deterministic_rollup(_obj5, [{"key": "a", "tier": "unknown"}])
    assert "fit_score" not in _obj5b, "all-unknown should omit fit_score"

    # -- run(): empty tile_contexts returns the "no data" shortcut with
    # a shaped skeleton — SPA can still render the panel structure.
    _empty = run(None, {"tile_contexts": []})
    assert "lens_insight" in _empty
    assert _empty["lens_insight"]["executive_summary"].startswith("No tile scoring")
    assert len(_empty["lens_insight"]["sections"]) == len(LENS_SECTION_MAP)
    for sec in _empty["lens_insight"]["sections"]:
        assert sec["verdict"] == "unknown"

    # -- run(): valid response path — one attempt, JSON parses, schema
    # passes, rollup overrides model verdict.
    class _GoodBackend:
        def __init__(self, payload_json: str):
            self.payload = payload_json
            self.calls = 0
        def generate_from_messages(self, msgs, **sampler):
            self.calls += 1
            return self.payload

    # Model returns an obj with the exemplar shape but wrong verdict on
    # section 0 — rollup will fix it from the input tiers.
    _model_out = json.loads(msgs[2]["content"])
    # Force a wrong verdict on Rail & regional — rollup should reset
    # to the actual tier in the ctx we pass.
    _model_out["sections"][0]["verdict"] = "red"
    _b = _GoodBackend(json.dumps(_model_out))
    # Provide input tile_contexts covering all 9 tiles with predictable
    # per-section rollup outcomes.
    _input_ctx = {
        "address_hint": {"bezirk": "Pankow", "ortsteil": "Prenzlauer Berg"},
        "tile_contexts": [
            {"key": "commuter_rail_transit", "tier": "green"},
            {"key": "regional_rail_reach", "tier": "amber"},
            {"key": "commuter_tram_transit", "tier": "green"},
            {"key": "commuter_bus_transit", "tier": "green"},
            {"key": "cycling_network", "tier": "green"},
            {"key": "car_sharing_reach", "tier": "green"},
            {"key": "ev_charging_reach", "tier": "green"},
            {"key": "airport_reach", "tier": "red"},
            {"key": "gesix_commuter", "tier": "green"},
        ],
    }
    _out = run(_b, _input_ctx)
    assert _b.calls == 1, "valid response should not retry"
    # Rail & regional [rail=green, regional=amber] → amber (worst wins).
    # Model had said 'red'; rollup should correct to 'amber'.
    assert _out["lens_insight"]["sections"][0]["verdict"] == "amber", \
        "Rail & regional should roll up to amber (worst of green+amber)"
    # Short-hop transit [tram=green, bus=green] → green.
    assert _out["lens_insight"]["sections"][1]["verdict"] == "green"
    # Cycling & car [all green] → green.
    assert _out["lens_insight"]["sections"][2]["verdict"] == "green"
    # Long-haul travel [airport=red] → red.
    assert _out["lens_insight"]["sections"][3]["verdict"] == "red"
    # Neighbourhood profile [gesix=green] → green.
    assert _out["lens_insight"]["sections"][4]["verdict"] == "green"
    # Fit score: (60+100+100+20+100)/5 = 76.
    assert _out["lens_insight"].get("fit_score") == 76, \
        _out["lens_insight"].get("fit_score")

    # -- run(): malformed JSON → retry once → raise on second failure.
    class _BadBackend:
        def __init__(self): self.calls = 0
        def generate_from_messages(self, msgs, **sampler):
            self.calls += 1
            return "not json at all"
    _bb = _BadBackend()
    try:
        run(_bb, _input_ctx)
    except ValueError as e:
        assert "invalid JSON twice" in str(e), str(e)
    else:
        raise AssertionError("expected ValueError after two failed attempts")
    assert _bb.calls == 2, "should have retried exactly once"

    # -- Non-dict ctx → ValueError.
    try:
        run(None, "not-a-dict")
    except ValueError as e:
        assert "object" in str(e)
    else:
        raise AssertionError("expected ValueError for non-dict ctx")

    print("lens_commuter_insight.py selfcheck OK")
