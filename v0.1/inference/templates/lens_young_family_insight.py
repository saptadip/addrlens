"""`lens_young_family_insight` — one-call lens-level executive summary for
the Young Family lens.

Consumes ALL 10 Young Family tile scoring outputs at once and returns a
strict-JSON response the SPA renders as the "AI Insight" panel above the
Young Family tile grid. Replaces the per-tile `Get Insight` buttons (one
call per tile, one Cloudflare hop per tile) with a single fan-in call
per lens.

Response schema:

    {
      "executive_summary": "<2-3 sentences of plain-English framing>",
      "sections": [
        {"title": "Kids & care",
         "tiles": ["kita", "playground", "pediatrician"],
         "verdict": "green|amber|red|unknown",
         "note": "<1 sentence>"},
        ...
      ],
      "highlights_green": [{"tile": "kita",
                            "one_line": "3 Kitas within 400 m"}, ...],
      "highlights_red":   [{"tile": "noise",
                            "one_line": "L_DEN 63 dB — traffic-facade"}, ...],
      "fit_score": 72
    }

Design notes
------------
- Sections are HARDCODED here in `LENS_SECTION_MAP`, not LLM-chosen. The
  LLM only fills `verdict` (rolled up over the section's tiles — worst
  wins), `note` (one sentence), and the highlight `one_line` fields. This
  makes the output validatable — reject responses whose section list
  drifts, whose keys don't match, or whose highlight tiles aren't in the
  input set.
- Verdict rollup is deterministic: after the LLM responds, `run()`
  overwrites the `verdict` field on each section from the input tile
  tiers (`red > amber > green > unknown` — worst wins). The model can't
  accidentally promote an amber section to green.
- No per-tile framing library. Callers pass tile facts (`label`, `tier`,
  `rule`, `numeric`, `caveat`) and the summariser works from those alone
  — the per-tile `*_insight.py` templates are being retired in the
  Route-B cleanup, so a runtime import would fail.
- No invention. System forbids citing facts absent from the payload.
- No inversion. All 10 Young Family tiles emit real tiers today; there
  are no info-only tiles in this lens. The `info` alias is still
  accepted for parity with the Newcomer template and future-proofing.
"""
from __future__ import annotations

import json

# Lower temp than tile insights — this is structured JSON output, not
# flowing prose. max_tokens is generous to fit 5 sections + up to 6
# highlights without truncation.
SAMPLER = {
    "temp":               0.35,
    "top_p":              0.9,
    "repetition_penalty": 1.1,
    # 1400 tokens covers a 10-tile lens payload with 5 sections + up to
    # 6 highlights without truncation on Cloudflare Llama-3.1-8B. Local
    # Qwen 1.5B (dev fallback) also fits — Young Family is smaller than
    # Newcomer (10 vs 13 tiles) so there's ample headroom.
    "max_tokens":         1400,
}

# Young Family lens tile groupings. Keys must match `LensTileConfig.key`
# in `app/cities/berlin.py::YOUNG_FAMILY_LENS`. Every tile must appear
# in exactly one section — the __main__ selfcheck enforces this.
LENS_SECTION_MAP: list[dict] = [
    {"title": "Kids & care",
     "tiles": ["kita", "playground", "pediatrician"]},
    {"title": "Daily transit",
     "tiles": ["transit"]},
    {"title": "Everyday errands",
     "tiles": ["supermarket"]},
    {"title": "Ambient environment",
     "tiles": ["noise", "air", "heat"]},
    {"title": "Green refuge & neighbourhood",
     "tiles": ["refuge", "gesix"]},
]

# Worst-tier-wins ordering. The scoring pipeline emits `green`,
# `amber`, `red`, and `unknown` only (see `app/core/scoring/constants.py`).
# `info` is accepted as an alias for `unknown` for parity with the
# Newcomer template — Young Family has no info-only tiles today, but
# accepting the alias future-proofs the rollup if a numeric-only tile
# is ever added. The `.get(tier, -1)` default excludes any non-ranked
# value from the rollup so a section of only unknown / info tiles rolls
# up to `unknown`.
_TIER_RANK = {"green": 0, "amber": 1, "red": 2, "unknown": -1}

# Fit score weights — used by `_compute_fit_score` after section rollup.
# Byte-for-byte parity with `lens_newcomer_insight._FIT_WEIGHTS` so the
# fit-score axis is comparable across lenses. green=100 (walkable/dense),
# amber=60 (walkable but not doorstep), red=20 (not zero because "far"
# still means SOME reach). Unknown / info sections excluded so they
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
    "You are writing a per-lens executive summary for the Young Family "
    "lens of a Berlin address-intelligence tool. The user is a parent "
    "or carer of children under six evaluating this address as a "
    "family home. You receive a JSON payload with: (a) the address's "
    "Bezirk / Ortsteil hint, (b) a list of 10 Young Family tile "
    "results, each carrying `key`, `label`, `tier` (green / amber / "
    "red / unknown / info), `rule`, `numeric`, and `caveat`. "
    "Return ONE JSON object with EXACTLY these top-level keys: "
    "`executive_summary` (string, 2-3 sentences), "
    "`sections` (array — see below), "
    "`highlights_green` (array of {tile, one_line}), "
    "`highlights_red` (array of {tile, one_line}). "
    "Rules for `executive_summary`: 2-3 sentences of plain English, "
    "60-100 words total. Frame the address as a family-home prospect — "
    "does the daily routine of a parent with young children work here? "
    "Cite the strongest 1-2 positives and the sharpest 1-2 concerns "
    "drawn from tiered tiles (green / amber / red). All 10 Young "
    "Family tiles carry real verdicts today — none are info-only, so "
    "every tile is eligible to be cited as a positive or concern. "
    "IMPORTANT — section names vs tile names: `expected_sections[].title` "
    "values ('Kids & care', 'Daily transit', 'Everyday errands', "
    "'Ambient environment', 'Green refuge & neighbourhood') are "
    "GROUPINGS for the `sections` field ONLY. They MUST NOT appear in "
    "the executive summary paragraph. In the summary, refer to each "
    "signal by its real-world function using the tile `label` (e.g., "
    "'Kita', 'playground', 'pediatrician', 'summer heat', 'street-"
    "tree canopy'), NOT the section title that contains it. Writing "
    "'Kids & care is strong' is WRONG — that conflates a section "
    "grouping with specific tiles. Write 'Kitas and a playground are "
    "within a stroller walk' instead. "
    "No German words except proper names (Bezirk, Ortsteil, Kita, "
    "Kiez are fine as terminology). "
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
    "distances, times, names, or dates. "
    "(2) Never promote a red or amber tile to green in `sections` or "
    "in the summary. "
    "(3) Do not editorialise about 'good' or 'bad' neighbourhoods. "
    "Describe, don't judge. "
    "(4) TONE DISCIPLINE per tier: green = clearly positive framing "
    "('close', 'dense', 'walkable', 'stroller-friendly', 'strong'). "
    "amber = neutral, situational framing ('walkable but not doorstep', "
    "'a short walk', '~10-minute walk', 'reachable with a stroller'). "
    "red = clearly negative framing ('far', 'lacks', 'no ... nearby', "
    "'expect a longer commute'). Do NOT use red-tier language ('far', "
    "'long distance', 'lacks') for amber tiles — amber is the middle "
    "ground, not a failure. A Kita 700 m away is amber ('a 10-minute "
    "stroller walk'), NOT 'far'. Reserve strong negative framing for "
    "tiles the payload actually marks red. "
    "(5) Return ONLY the JSON object. No preamble, no code fences, no "
    "trailing prose."
)


def _build_tile_payload(tile_contexts: list[dict]) -> list[dict]:
    """Trim each tile_context to the fields the summariser needs. Drops
    `features`, `sources`, `legend`, `framing` — the summariser reads
    only the verdict axis, not the tile drill-down. No dynamic import
    of sibling `*_insight.py` templates: those are being retired in the
    Route-B cleanup, and this template must survive their removal."""
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
          {"key": "kita", "label": "Kita reachability",
           "tier": "green", "rule": "≥3 within 400 m OR ≤400 m",
           "numeric": "3 kitas within 400 m",
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

    # Compact one-shot exemplar. Full 10-tile listing dropped to keep
    # the prompt small enough for local Qwen 1.5B (n_ctx=4096); the
    # system prompt names the schema, the assistant reply demonstrates
    # the fill-in pattern. Genericised placeholders — a real bezirk /
    # ortsteil in the exemplar was being copied into the response by
    # smaller models on the Newcomer template, corrupting the address
    # hint; mirror that fix here.
    exemplar_user = json.dumps({
        "address_hint": {"bezirk": "<Bezirk from payload>",
                          "ortsteil": "<Ortsteil from payload>"},
        "expected_sections": LENS_SECTION_MAP,
        "tiles": "<10 Young Family tiles with key/tier/rule/numeric/caveat>",
    }, ensure_ascii=False)

    exemplar_assistant = json.dumps({
        "executive_summary": (
            "This Ortsteil works as a family home: three Kitas and a "
            "playground sit within a stroller walk, and a pediatrician "
            "is 600 m from the door. Façade noise is elevated at 62 dB "
            "L_DEN — plan for a bedroom on the courtyard side. The "
            "socioeconomic profile of the Planungsraum is mid-range, "
            "and the nearest quiet-zone green refuge is a 15-minute walk."
        ),
        "sections": [
            {"title": "Kids & care",
             "tiles": ["kita", "playground", "pediatrician"],
             "verdict": "green",
             "note": "Kita, playground, and pediatrician all within a stroller walk."},
            {"title": "Daily transit",
             "tiles": ["transit"],
             "verdict": "green",
             "note": "Nearest S-Bahn stop is a 4-minute walk."},
            {"title": "Everyday errands",
             "tiles": ["supermarket"],
             "verdict": "green",
             "note": "Supermarket within a 5-minute walk."},
            {"title": "Ambient environment",
             "tiles": ["noise", "air", "heat"],
             "verdict": "amber",
             "note": "Façade noise is elevated; air and heat sit in the moderate band."},
            {"title": "Green refuge & neighbourhood",
             "tiles": ["refuge", "gesix"],
             "verdict": "amber",
             "note": "Quiet zone is a 15-minute walk; socioeconomic profile is mid-range."},
        ],
        "highlights_green": [
            {"tile": "kita",
             "one_line": "Three Kitas within a 400 m stroller walk."},
            {"tile": "pediatrician",
             "one_line": "Nearest pediatrician 600 m from the door."},
            {"tile": "transit",
             "one_line": "S-Bahn stop a 4-minute walk away."},
        ],
        "highlights_red": [
            {"tile": "noise",
             "one_line": "Façade noise 62 dB L_DEN — plan bedrooms on the courtyard side."},
            {"tile": "refuge",
             "one_line": "Nearest quiet-zone green refuge is a 15-minute walk."},
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
    # highlights_* are optional but if present must be lists of {tile, one_line}
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
    (5) Emit `fit_score` (0-100) computed from the deterministic section
        verdicts. Skipped if all sections roll up to unknown.

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
                continue                          # highlight tile not in input
            if tile.get("tier") not in allowed_tiers:
                continue                          # tone mismatch
            keep.append(h)
        return keep

    if "highlights_green" in obj:
        obj["highlights_green"] = _filter_hi(obj["highlights_green"], {"green"})
    if "highlights_red" in obj:
        obj["highlights_red"] = _filter_hi(obj["highlights_red"], {"amber", "red"})

    # Dedup — same tile can't be both green and red. Green wins (the tier
    # data proves it's green, so a red claim there is definitionally
    # wrong).
    if obj.get("highlights_green") and obj.get("highlights_red"):
        green_keys = {h.get("tile") for h in obj["highlights_green"]}
        obj["highlights_red"] = [h for h in obj["highlights_red"]
                                 if h.get("tile") not in green_keys]

    # Fit score — computed AFTER rollup so it reflects deterministic
    # verdicts, not the LLM's guesses. Skipped if all sections roll up
    # to unknown (score field omitted → frontend hides the chip).
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
        f"lens_young_family_insight: model returned invalid JSON twice "
        f"({type(last_err).__name__}: {last_err})"
    )


if __name__ == "__main__":
    # -- LENS_SECTION_MAP covers all 10 Young Family tile keys, no orphans,
    # no duplicates. If a new YF tile lands in berlin.py without a section
    # entry, this assert fails at boot.
    _yf_tile_keys = {
        "kita", "playground", "pediatrician",
        "transit", "supermarket",
        "noise", "air", "heat",
        "refuge", "gesix",
    }
    _mapped = []
    for sec in LENS_SECTION_MAP:
        _mapped.extend(sec["tiles"])
    assert set(_mapped) == _yf_tile_keys, \
        f"LENS_SECTION_MAP diverges from Young Family tile keys — " \
        f"missing: {_yf_tile_keys - set(_mapped)}, " \
        f"extra: {set(_mapped) - _yf_tile_keys}"
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
    # user carries the address_hint and the tile list.
    _ctx = {
        "address_hint": {"bezirk": "Pankow", "ortsteil": "Prenzlauer Berg"},
        "tile_contexts": [
            {"key": "kita", "label": "Kita reachability",
             "tier": "green", "rule": "≥3 within 400 m OR ≤400 m",
             "numeric": "3 Kitas within 400 m"},
            {"key": "noise", "label": "Façade noise",
             "tier": "red", "rule": "≤55 dB green · ≤60 dB amber",
             "numeric": "62 dB L_DEN"},
        ],
    }
    msgs = build_messages(_ctx)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"], \
        [m["role"] for m in msgs]
    # System prompt names the four JSON keys and the anti-invention /
    # anti-inversion rules — these are the load-bearing constraints;
    # a future edit that drops them silently degrades output quality.
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
    # paragraph (would conflate "Kids & care" section with the specific
    # "kita" / "playground" / "pediatrician" tiles it contains).
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
    assert "noise" in _real_user
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
    # Realistic Young Family scenario: strong Kids & care + transit +
    # errands (green), amber environment, amber refuge/neighbourhood.
    # → (100 + 100 + 100 + 60 + 60) / 5 = 84.
    _yf_scenario = [{"verdict": "green"}, {"verdict": "green"},
                    {"verdict": "green"}, {"verdict": "amber"},
                    {"verdict": "amber"}]
    assert _compute_fit_score(_yf_scenario) == 84, _compute_fit_score(_yf_scenario)
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

    # Model returns an obj with the exemplar shape but wrong verdicts on
    # some sections — rollup will fix them from the input tiers.
    _model_out = json.loads(msgs[2]["content"])
    # Force a wrong verdict on Kids & care — rollup should reset to
    # whatever the actual tier is in the ctx we pass.
    _model_out["sections"][0]["verdict"] = "red"
    _b = _GoodBackend(json.dumps(_model_out))
    # Provide input tile_contexts matching the exemplar's ordering + tiers
    # so the rollup produces a predictable per-section verdict.
    _input_ctx = {
        "address_hint": {"bezirk": "Pankow", "ortsteil": "Prenzlauer Berg"},
        "tile_contexts": [
            {"key": "kita",         "tier": "green"},
            {"key": "playground",   "tier": "green"},
            {"key": "pediatrician", "tier": "green"},
            {"key": "transit",      "tier": "green"},
            {"key": "supermarket",  "tier": "green"},
            {"key": "noise",        "tier": "red"},
            {"key": "air",          "tier": "amber"},
            {"key": "heat",         "tier": "amber"},
            {"key": "refuge",       "tier": "amber"},
            {"key": "gesix",        "tier": "amber"},
        ],
    }
    _out = run(_b, _input_ctx)
    assert _b.calls == 1, "valid response should not retry"
    # Kids & care [kita=green, playground=green, pediatrician=green] → green.
    assert _out["lens_insight"]["sections"][0]["verdict"] == "green", \
        "rollup should have overridden 'red' back to 'green' for Kids & care"
    # Ambient environment [noise=red, air=amber, heat=amber] → red.
    assert _out["lens_insight"]["sections"][3]["verdict"] == "red", \
        "Ambient environment rolls up to red because noise is red"
    # Green refuge & neighbourhood [refuge=amber, gesix=amber] → amber.
    assert _out["lens_insight"]["sections"][4]["verdict"] == "amber", \
        "Green refuge & neighbourhood rolls up to amber"
    # Fit score: (100+100+100+60+20) / 5 = 76.
    assert _out["lens_insight"]["fit_score"] == 76, \
        _out["lens_insight"]["fit_score"]

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

    print("lens_young_family_insight.py selfcheck OK")
