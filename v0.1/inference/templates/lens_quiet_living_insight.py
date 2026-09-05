"""`lens_quiet_living_insight` — one-call lens-level executive summary
for the Quiet Living lens.

Mirrors the Newcomer summariser architecture (schema, deterministic
rollup, highlight-tone filter, fit_score, two-attempt retry) with three
Quiet-Living-specific adaptations:
- Audience framing: people prioritising a calm, low-noise home.
- Nine tiles grouped into four sections by user concern.
- Inverted-signal handling: `arterial_road`, `rail_noise`,
  `nightlife_inverted` all read "further / fewer is better" — the
  summary must not frame the raw number as "far / lacking".

DOES NOT dynamically import sibling `*_insight.py` templates for
framing. Those per-tile templates are being retired in the same cleanup
that promotes the per-lens AI panel to default. This template consumes
only the tile payload fields the app proxy already sends: `label`,
`tier`, `rule`, `numeric`, `caveat`.

Response schema (identical to Newcomer):

    {
      "executive_summary": "<2-3 sentences>",
      "sections": [
        {"title": "Ambient noise & air",
         "tiles": ["noise", "air"],
         "verdict": "green|amber|red|unknown",
         "note": "<1 sentence>"},
        ...
      ],
      "highlights_green": [{"tile": "quiet_zone",
                            "one_line": "620 m to nearest Ruhige Gebiete zone."}, ...],
      "highlights_red":   [{"tile": "arterial_road",
                            "one_line": "Arterial 40 m away — traffic pressure daily."}, ...],
      "fit_score": 0-100    # deterministic rollup, omitted when all-unknown
    }
"""
from __future__ import annotations

import json

SAMPLER = {
    "temp":               0.35,
    "top_p":              0.9,
    "repetition_penalty": 1.1,
    # 1400 tokens covers a 9-tile lens payload with 4 sections + up to
    # 6 highlights without truncation on Cloudflare Llama-3.1-8B-fast.
    "max_tokens":         1400,
}

# Quiet Living tile groupings. Every key must match a tile emitted by
# `quiet_living_lens` in app/core/lenses/quiet_living.py. The __main__
# selfcheck's completeness assert enforces coverage.
LENS_SECTION_MAP: list[dict] = [
    {"title": "Ambient noise & air",
     "tiles": ["noise", "air"]},
    {"title": "Green refuge",
     "tiles": ["quiet_zone", "street_trees"]},
    {"title": "Traffic pressure",
     "tiles": ["tempo30", "arterial_road", "rail_noise"]},
    {"title": "Neighbourhood profile",
     "tiles": ["nightlife_inverted", "gesix_quiet"]},
]

# Worst-tier-wins ordering. The Quiet Living scoring pipeline emits
# `green`, `amber`, `red`, `unknown` only — no info-only tiles today.
# `info` is accepted as an alias for `unknown` for parity with the
# Newcomer template (a future numeric-only QL tile would land here).
# The `.get(tier, -1)` default excludes any non-ranked value from
# rollup so a section of only unknown/info tiles rolls up to `unknown`.
_TIER_RANK = {"green": 0, "amber": 1, "red": 2, "unknown": -1}

# Fit score weights — parity with lens_newcomer_insight so scores are
# comparable across lenses. green=100 (calm/buffered), amber=60 (moderate,
# situational), red=20 (noisy/high pressure — not zero because even a
# red-noise address usually has some quiet refuges within reach).
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
    "You are writing a per-lens executive summary for the Quiet Living "
    "lens of a Berlin address-intelligence tool. The user is someone "
    "who prioritises a calm, low-noise home — sleep quality, low "
    "ambient noise, and access to quiet refuges matter more than "
    "commute speed or nightlife. You receive a JSON payload with: "
    "(a) the address's Bezirk / Ortsteil hint, (b) a list of 9 Quiet "
    "Living tile results, each carrying `key`, `label`, `tier` "
    "(green / amber / red / unknown), `rule`, `numeric`, and `caveat`. "
    "Return ONE JSON object with EXACTLY these top-level keys: "
    "`executive_summary` (string, 2-3 sentences), "
    "`sections` (array — see below), "
    "`highlights_green` (array of {tile, one_line}), "
    "`highlights_red` (array of {tile, one_line}). "
    "Rules for `executive_summary`: 2-3 sentences of plain English, "
    "60-100 words total. Frame the address as a calm-living prospect. "
    "Cite the strongest 1-2 positives and the sharpest 1-2 concerns "
    "drawn from tiered tiles (green / amber / red). "
    "IMPORTANT — section names vs tile names: `expected_sections[].title` "
    "values ('Ambient noise & air', 'Green refuge', 'Traffic pressure', "
    "'Neighbourhood profile') are GROUPINGS for the `sections` field "
    "ONLY. They MUST NOT appear in the executive summary paragraph. "
    "In the summary, refer to each signal by its real-world function "
    "using the tile `label` (e.g., 'façade noise', 'nearest quiet "
    "zone', 'street-tree canopy', 'arterial road'), NOT the section "
    "title that contains it. Writing 'The Traffic pressure is high' "
    "is WRONG — that conflates a section grouping with specific tiles. "
    "Write 'The nearest arterial road is 40 m away' instead. "
    "IMPORTANT — INVERTED signals: some tiles measure distance FROM a "
    "noise source or COUNT of a nuisance — the green tier means far / "
    "few of them, which is the desired state. `arterial_road`, "
    "`rail_noise`, and `nightlife_inverted` are inverted (further / "
    "fewer is better). If the tile's `caveat` mentions 'INVERTED' or "
    "'further is better' or 'fewer is better', do NOT describe a green "
    "reading as 'far / lacking' — describe it as 'buffered from', "
    "'well set back from', or 'few venues nearby'. A green "
    "`arterial_road` result should read 'buffered from arterial "
    "traffic', NOT 'far from any major road'. "
    "No German words except proper names (Bezirk, Ortsteil, Kiez, "
    "Ruhige Gebiete, Straßenbäume are fine as terminology). "
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
    "('quiet', 'calm', 'buffered', 'well set back'). amber = neutral, "
    "situational framing ('moderate', 'occasional', 'some traffic "
    "pressure', 'a short walk away'). red = clearly negative framing "
    "('noisy', 'high traffic', 'immediately next to', 'lacks a quiet "
    "zone within reach'). Do NOT use red-tier language ('noisy', "
    "'high traffic') for amber tiles — amber is the middle ground, "
    "not a failure. An arterial road 100 m away is amber ('some "
    "traffic pressure nearby'), NOT 'immediately next to a highway'. "
    "Reserve strong negative framing for tiles the payload actually "
    "marks red. "
    "(5) Return ONLY the JSON object. No preamble, no code fences, no "
    "trailing prose."
)


def _build_tile_payload(tile_contexts: list[dict]) -> list[dict]:
    """Trim each tile_context to the fields the summariser needs. Drops
    `features`, `sources`, `legend`, `framing` — the summariser reads
    only the verdict axis + caveat (used to spot INVERTED signals).
    A tile missing `key` is dropped — the summariser is keyed on
    `LENS_SECTION_MAP` which enumerates the tile keys."""
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
          {"key": "noise", "label": "Façade noise",
           "tier": "amber", "rule": "≤55 dB L_DEN green · ≤60 dB amber",
           "numeric": "58 dB L_DEN", "caveat": None},
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

    # Compact placeholder exemplar_user — full 9-tile listing dropped to
    # keep the prompt lean. Genericised bezirk / ortsteil so smaller
    # models don't copy the exemplar's address into the response.
    exemplar_user = json.dumps({
        "address_hint": {"bezirk": "<Bezirk from payload>",
                          "ortsteil": "<Ortsteil from payload>"},
        "expected_sections": LENS_SECTION_MAP,
        "tiles": "<9 Quiet Living tiles with key/tier/rule/numeric/caveat>",
    }, ensure_ascii=False)

    exemplar_assistant = json.dumps({
        "executive_summary": (
            "This Ortsteil reads mixed on the Quiet Living axes: façade "
            "noise sits at 58 dB L_DEN and the nearest arterial road is "
            "80 m away, so the block carries some traffic pressure during "
            "the day. On the calmer side, a designated Ruhige Gebiete "
            "zone is a 10-minute walk and street-tree canopy is dense — "
            "so the daily buffer is close even if the front door faces a "
            "busier street."
        ),
        "sections": [
            {"title": "Ambient noise & air", "tiles": ["noise", "air"],
             "verdict": "amber",
             "note": "Façade noise is moderate; air is within WHO daytime bounds."},
            {"title": "Green refuge",
             "tiles": ["quiet_zone", "street_trees"],
             "verdict": "green",
             "note": "Designated quiet zone reachable on foot; canopy is dense on the block."},
            {"title": "Traffic pressure",
             "tiles": ["tempo30", "arterial_road", "rail_noise"],
             "verdict": "amber",
             "note": "30 km/h street; arterial buffered but present; rail is well set back."},
            {"title": "Neighbourhood profile",
             "tiles": ["nightlife_inverted", "gesix_quiet"],
             "verdict": "green",
             "note": "Few late-night venues within 300 m; socioeconomic profile stable."},
        ],
        "highlights_green": [
            {"tile": "quiet_zone",
             "one_line": "Ruhige Gebiete zone 620 m from the door."},
            {"tile": "street_trees",
             "one_line": "Street-tree canopy at 11% — tree-dense for a Straßenbäume signal."},
            {"tile": "nightlife_inverted",
             "one_line": "Only 2 late-night venues within 300 m — few sleep disruptions."},
        ],
        "highlights_red": [
            {"tile": "noise",
             "one_line": "Façade noise at 58 dB L_DEN — moderate but audible."},
            {"tile": "arterial_road",
             "one_line": "Arterial road 80 m away — some traffic pressure on the block."},
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
    (3) Filter `highlights_red` so only tiles with `tier` in `{"amber",
        "red"}` survive; drop unknown / green / info tiles.
    (4) Dedup: if the same tile lands in both green and red lists (LLM
        confusion), keep the green entry and drop from red.
    (5) Emit `fit_score` (0-100) computed from the deterministic
        verdicts. Omitted when all sections roll up to unknown."""
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
    verdict rollup + highlight filter + fit_score. Malformed JSON or
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
        f"lens_quiet_living_insight: model returned invalid JSON twice "
        f"({type(last_err).__name__}: {last_err})"
    )


if __name__ == "__main__":
    # -- LENS_SECTION_MAP covers all 9 Quiet Living tile keys, no
    # orphans, no duplicates. Guards against a new QL tile landing in
    # berlin.py without a section entry.
    _ql_tile_keys = {
        "noise", "air", "quiet_zone", "street_trees",
        "tempo30", "arterial_road", "rail_noise",
        "nightlife_inverted", "gesix_quiet",
    }
    _mapped = []
    for sec in LENS_SECTION_MAP:
        _mapped.extend(sec["tiles"])
    assert set(_mapped) == _ql_tile_keys, \
        f"LENS_SECTION_MAP diverges from Quiet Living tile keys — " \
        f"missing: {_ql_tile_keys - set(_mapped)}, " \
        f"extra: {set(_mapped) - _ql_tile_keys}"
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
            {"key": "noise", "label": "Façade noise",
             "tier": "amber", "rule": "≤55 dB green",
             "numeric": "58 dB L_DEN"},
            {"key": "arterial_road", "label": "Distance to arterial road",
             "tier": "red", "rule": "≥150 m green",
             "numeric": "40 m", "caveat": "INVERTED signal — further is better"},
        ],
    }
    msgs = build_messages(_ctx)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"], \
        [m["role"] for m in msgs]

    # System prompt must name the four JSON keys + all guardrails.
    _sys = msgs[0]["content"]
    for _key in ("executive_summary", "sections", "highlights_green", "highlights_red"):
        assert _key in _sys, f"system prompt missing schema key: {_key}"
    assert "Never invent" in _sys or "never invent" in _sys.lower(), \
        "system must forbid invention"
    assert "Never promote" in _sys or "never promote" in _sys.lower(), \
        "system must forbid tier promotion (anti-inversion)"
    assert "no code fences" in _sys.lower() or "no preamble" in _sys.lower(), \
        "system must forbid markdown wrapper prose"
    assert "tone discipline" in _sys.lower(), \
        "system must carry per-tier tone discipline rule"
    assert "amber" in _sys.lower() and "middle ground" in _sys.lower(), \
        "system must explicitly frame amber as the middle ground"
    assert "section names vs tile names" in _sys.lower(), \
        "system must forbid section titles in the summary paragraph"
    # Inverted-signal handling is the load-bearing QL-specific guardrail.
    assert "inverted" in _sys.lower(), \
        "system must handle INVERTED signals (arterial_road, rail_noise, nightlife_inverted)"
    assert "buffered" in _sys.lower(), \
        "system must model correct inverted-signal framing (e.g. 'buffered from')"

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
    assert "arterial_road" in _real_user
    assert '"expected_sections"' in _real_user, \
        "real user payload must include expected_sections (shape lock)"
    # Caveat travels so INVERTED signals can be detected by the model.
    assert "INVERTED" in _real_user, \
        "caveat with INVERTED marker must round-trip in the payload"

    # -- _validate_shape happy path + failure modes.
    _good = json.loads(msgs[2]["content"])
    _validate_shape(_good)

    _bad_title = json.loads(msgs[2]["content"])
    _bad_title["sections"][0]["title"] = "Something else"
    try:
        _validate_shape(_bad_title)
    except ValueError as e:
        assert "title drifted" in str(e)
    else:
        raise AssertionError("expected ValueError on section title drift")

    _bad_tiles = json.loads(msgs[2]["content"])
    _bad_tiles["sections"][0]["tiles"] = ["something_else"]
    try:
        _validate_shape(_bad_tiles)
    except ValueError as e:
        assert "tiles drifted" in str(e)
    else:
        raise AssertionError("expected ValueError on section tile drift")

    _bad_len = json.loads(msgs[2]["content"])
    _bad_len["sections"] = _bad_len["sections"][:2]
    try:
        _validate_shape(_bad_len)
    except ValueError as e:
        assert "length" in str(e)
    else:
        raise AssertionError("expected ValueError on wrong sections length")

    _bad_exec = json.loads(msgs[2]["content"])
    _bad_exec.pop("executive_summary")
    try:
        _validate_shape(_bad_exec)
    except ValueError as e:
        assert "executive_summary" in str(e)
    else:
        raise AssertionError("expected ValueError on missing executive_summary")

    _bad_hi = json.loads(msgs[2]["content"])
    _bad_hi["highlights_green"][0].pop("tile")
    try:
        _validate_shape(_bad_hi)
    except ValueError as e:
        assert "tile" in str(e)
    else:
        raise AssertionError("expected ValueError on bad highlight shape")

    # -- _apply_deterministic_rollup overrides section verdict from the
    # input tile tiers.
    _obj = {"sections": [
        {"title": "T1", "tiles": ["a", "b"], "verdict": "green", "note": "..."},
    ]}
    _tcs = [{"key": "a", "tier": "green"}, {"key": "b", "tier": "red"}]
    _obj2 = _apply_deterministic_rollup(_obj, _tcs)
    assert _obj2["sections"][0]["verdict"] == "red", \
        f"rollup should have promoted section to red, got {_obj2['sections'][0]['verdict']!r}"

    # -- Highlight tone filter: same semantics as Newcomer.
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
    # QL scenario: 4 sections rolling up to amber, green, amber, green
    # → (60+100+60+100)/4 = 80. This is a "balanced" fit — matches the
    # exemplar_assistant story above.
    _ql_sample = [{"verdict": "amber"}, {"verdict": "green"},
                  {"verdict": "amber"}, {"verdict": "green"}]
    assert _compute_fit_score(_ql_sample) == 80, _compute_fit_score(_ql_sample)

    # Rollup output carries fit_score post-computation.
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

    # -- run(): empty tile_contexts returns the shortcut skeleton.
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

    _model_out = json.loads(msgs[2]["content"])
    _model_out["sections"][0]["verdict"] = "red"     # force wrong verdict
    _b = _GoodBackend(json.dumps(_model_out))
    _input_ctx = {
        "address_hint": {"bezirk": "Pankow", "ortsteil": "Prenzlauer Berg"},
        "tile_contexts": [
            {"key": "noise", "tier": "amber"},
            {"key": "air", "tier": "green"},
            {"key": "quiet_zone", "tier": "green"},
            {"key": "street_trees", "tier": "green"},
            {"key": "tempo30", "tier": "green"},
            {"key": "arterial_road", "tier": "amber"},
            {"key": "rail_noise", "tier": "green"},
            {"key": "nightlife_inverted", "tier": "green"},
            {"key": "gesix_quiet", "tier": "green"},
        ],
    }
    _out = run(_b, _input_ctx)
    assert _b.calls == 1, "valid response should not retry"
    # Section 0 (noise/air) → worst of amber/green = amber (model said red,
    # rollup corrected).
    assert _out["lens_insight"]["sections"][0]["verdict"] == "amber", \
        f"rollup should have overridden model 'red' to 'amber', got " \
        f"{_out['lens_insight']['sections'][0]['verdict']!r}"
    # Section 2 (traffic pressure = tempo30 green + arterial amber + rail
    # green) rolls up to amber.
    assert _out["lens_insight"]["sections"][2]["verdict"] == "amber", \
        "Traffic pressure rolls up to amber from arterial_road amber"
    # Section 3 (neighbourhood profile = nightlife_inverted green + gesix
    # green) rolls up to green.
    assert _out["lens_insight"]["sections"][3]["verdict"] == "green", \
        "Neighbourhood profile rolls up to green from both nightlife and gesix"
    # Fit score = (amber, green, amber, green) → (60+100+60+100)/4 = 80.
    assert _out["lens_insight"].get("fit_score") == 80, \
        f"fit_score should be 80 for this scenario, got {_out['lens_insight'].get('fit_score')}"

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

    print("lens_quiet_living_insight.py selfcheck OK")
