"""Shared scaffolding for tier-plus-features insight templates.

Sixteen `*_insight` templates share an identical ~40-line pattern:

    SAMPLER = {"temp": 0.4, "top_p": 0.9,
               "repetition_penalty": 1.15, "max_tokens": 320}
    _SYSTEM = "<per-tile system prompt>"

    def build_messages(ctx):
        facts = json.dumps({
            "tier": ctx.get("tier"), "rule": ctx.get("rule"),
            "numeric": ctx.get("numeric"),
            "top": (ctx.get("features") or [])[:N],
        }, ensure_ascii=False, indent=2)
        return [system, exemplar_user, exemplar_assistant, {user: facts}]

    def run(backend, ctx):
        if not isinstance(ctx, dict): raise ValueError(...)
        if not (ctx.get("features") or []):
            return {"insight": <empty-msg>}
        return {"insight": backend.generate_from_messages(msgs, **SAMPLER)}

Silent drift had already crept in — the reviewer flagged that
`refuge_insight.py` uses a `plr_hint` key not present elsewhere and
that some tiles slice `[:5]` while transit tiles slice `[:6]`. The
shared base captures the invariant (facts shape, sampler defaults,
empty-features shortcut) so the drift class disappears; per-tile
divergences (top-K, system prompt, exemplars, empty message) stay
as parameters.

Six templates do NOT use this scaffold — they carry legitimately
different context shapes and stay standalone:

- `air_insight`, `heat_insight`, `noise_insight` — aggregate readings
  (`no2_ugm3`, `day_class`, `l_den`), no `features` list.
- `gesix_insight`, `gesix_newcomer_insight` — quintile + rank shape;
  anti-inversion asserts on negative-mode inputs are load-bearing per
  `CLAUDE.md`, per-template selfcheck stays pinned.
- `refuge_insight` — composite `quiet + trees` shape with its own
  empty-both-signals language.

Selfchecks stay per-tile: each template's `__main__` block still
verifies its own system-prompt content, its exemplar shape, and any
anti-inversion or "no invention" guarantees. The base module has its
own selfcheck for the shared plumbing (facts JSON shape, empty
shortcut, top-K slicing).
"""
from __future__ import annotations

import json
from typing import Any, Callable

# Every migrated template used this exact sampler. Any tile that needs
# a different knob should pass its own `sampler=` explicitly to
# `run_tier` — the default is preserved so byte-exact prompts survive.
DEFAULT_SAMPLER: dict = {
    "temp":               0.4,
    "top_p":              0.9,
    "repetition_penalty": 1.15,
    "max_tokens":         320,
}


def build_tier_messages(
    *,
    system: str,
    exemplar_user: str,
    exemplar_assistant: str,
    ctx: dict,
    top_k: int = 5,
) -> list[dict]:
    """Build the standard 4-message list: system, exemplar user,
    exemplar assistant, real user facts.

    `ctx` is inspected for the standard `tier` / `rule` / `numeric` /
    `features` keys; whichever are absent become `None` in the facts
    JSON so the model sees explicit gaps.
    """
    facts = json.dumps({
        "tier":    ctx.get("tier"),
        "rule":    ctx.get("rule"),
        "numeric": ctx.get("numeric"),
        "top":     (ctx.get("features") or [])[:top_k],
    }, ensure_ascii=False, indent=2)
    return [
        {"role": "system",    "content": system},
        {"role": "user",      "content": exemplar_user},
        {"role": "assistant", "content": exemplar_assistant},
        {"role": "user",      "content": facts},
    ]


def run_tier(
    backend: Any,
    ctx: dict,
    *,
    system: str,
    exemplar_user: str,
    exemplar_assistant: str,
    empty_msg: str,
    top_k: int = 5,
    sampler: dict | None = None,
) -> dict:
    """Standard tier-tile run entry point.

    Returns `{"insight": "<text>"}` on success, `{"insight": empty_msg}`
    on the empty-features shortcut, and raises `ValueError` on bad
    context — matching the pre-extraction behaviour of every tile.
    """
    if not isinstance(ctx, dict):
        raise ValueError("context must be an object")
    if not (ctx.get("features") or []):
        return {"insight": empty_msg}
    msgs = build_tier_messages(
        system             = system,
        exemplar_user      = exemplar_user,
        exemplar_assistant = exemplar_assistant,
        ctx                = ctx,
        top_k              = top_k,
    )
    text = backend.generate_from_messages(msgs, **(sampler or DEFAULT_SAMPLER))
    return {"insight": text}


if __name__ == "__main__":
    # -- build_tier_messages: 4 messages, roles in fixed order --------
    msgs = build_tier_messages(
        system             = "SYS",
        exemplar_user      = "EX_USER",
        exemplar_assistant = "EX_ASSIST",
        ctx                = {"tier": "green", "rule": "R", "numeric": "N",
                              "features": [{"n": 1}, {"n": 2}, {"n": 3}]},
    )
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"], msgs
    assert msgs[0]["content"] == "SYS"
    assert msgs[1]["content"] == "EX_USER"
    assert msgs[2]["content"] == "EX_ASSIST"

    # Real user message is JSON of the facts.
    facts = json.loads(msgs[3]["content"])
    assert facts["tier"]    == "green"
    assert facts["rule"]    == "R"
    assert facts["numeric"] == "N"
    assert facts["top"] == [{"n": 1}, {"n": 2}, {"n": 3}]

    # -- top_k slices features; missing features → empty list ---------
    msgs = build_tier_messages(
        system="s", exemplar_user="u", exemplar_assistant="a",
        ctx={"features": [{"n": i} for i in range(10)]},
        top_k=6,
    )
    assert len(json.loads(msgs[3]["content"])["top"]) == 6

    # Missing 'features' key → empty list, not KeyError.
    msgs = build_tier_messages(
        system="s", exemplar_user="u", exemplar_assistant="a",
        ctx={"tier": "red"},
    )
    assert json.loads(msgs[3]["content"])["top"] == []

    # -- run_tier: happy path calls backend, empty shortcut returns msg
    class _FakeBackend:
        def generate_from_messages(self, msgs, **sampler):
            self.last_msgs = msgs
            self.last_sampler = sampler
            return "generated text"

    b = _FakeBackend()
    out = run_tier(
        b, {"features": [{"n": 1}], "tier": "green"},
        system="s", exemplar_user="u", exemplar_assistant="a",
        empty_msg="none nearby",
    )
    assert out == {"insight": "generated text"}, out
    # Default sampler dispatched to backend.
    assert b.last_sampler == DEFAULT_SAMPLER
    assert len(b.last_msgs) == 4

    # Empty features → shortcut, no backend call.
    b2 = _FakeBackend()
    out = run_tier(
        b2, {"features": [], "tier": "red"},
        system="s", exemplar_user="u", exemplar_assistant="a",
        empty_msg="none nearby",
    )
    assert out == {"insight": "none nearby"}, out
    assert not hasattr(b2, "last_msgs"), "backend must not be called on empty features"

    # Missing 'features' key entirely also triggers shortcut.
    b3 = _FakeBackend()
    out = run_tier(
        b3, {"tier": "red"},
        system="s", exemplar_user="u", exemplar_assistant="a",
        empty_msg="none nearby",
    )
    assert out == {"insight": "none nearby"}

    # Non-dict ctx → ValueError.
    try:
        run_tier(_FakeBackend(), "not-a-dict",
                 system="s", exemplar_user="u", exemplar_assistant="a",
                 empty_msg="")
    except ValueError as e:
        assert "object" in str(e)
    else:
        raise AssertionError("expected ValueError for non-dict ctx")

    # Custom sampler override dispatched verbatim.
    b4 = _FakeBackend()
    override = {"temp": 0.7, "top_p": 0.95, "repetition_penalty": 1.0, "max_tokens": 64}
    run_tier(
        b4, {"features": [{"n": 1}]},
        system="s", exemplar_user="u", exemplar_assistant="a",
        empty_msg="", sampler=override,
    )
    assert b4.last_sampler == override

    print("_insight_base.py selfcheck OK")
