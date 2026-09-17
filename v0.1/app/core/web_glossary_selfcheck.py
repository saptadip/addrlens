"""Assert every TILE_GLOSSARY_KEYS reference resolves in GLOSSARY.

Both dicts live in `web/static/modules/constants.js` and are consumed
by the frontend at tooltip-render time. When a new tile registers
glossary keys in `TILE_GLOSSARY_KEYS` but forgets to add the matching
definitions to `GLOSSARY`, the tooltip silently renders `—` for each
orphan reference — a bug the CI cannot see because the frontend has
no test suite and the failure mode is a missing dict lookup, not a
runtime error.

PR #74 (cobblestone_nearby tile) shipped exactly this class of bug —
`Kopfsteinpflaster`, `Sett`, `Pflaster` were registered but not
defined; PR #75 patched the definitions in and a code-reviewer
follow-up called for a CI lint so the next occurrence gets caught at
the matrix stage, not in production.

Pure — no network, no server. Reads one file, parses two dicts with
regex, asserts coverage. Runs under 50 ms.

Cost of a false negative (bug slips through): a tile ships with dead
tooltips until a user complains.

Cost of a false positive (this lint fails on a formatting change to
constants.js): the reviewer will notice within one CI run and either
fix the definition or teach this parser about the new shape. Regex
brittleness is capped by the two dict extractors returning None → an
explicit AssertionError with the file path, not a silent skip.
"""
from __future__ import annotations

import re
from pathlib import Path


# Resolve the frontend constants.js off this file's location so the
# selfcheck runs identically from any working directory (local `python
# -m app.core.web_glossary_selfcheck` and the CI matrix's cwd=v0.1).
_CONSTANTS_JS = (Path(__file__).resolve().parents[2]
                 / "web" / "static" / "modules" / "constants.js")


def _strip_line_comments(text: str) -> str:
    """Drop `//` line comments so quoted strings inside them don't
    contaminate key extraction. Block comments (`/* ... */`) are not
    used in constants.js — verified as of writing; if a future edit
    adds one, the two `_extract_*_dict_body` calls will still work
    because they bound on `\\n};` which no comment straddles."""
    return "\n".join(re.sub(r"//.*$", "", line) for line in text.splitlines())


def _extract_dict_body(text: str, dict_name: str) -> str:
    """Return the `{ ... }` body of `export const <dict_name> = { ... };`.
    Non-greedy match on `\\n};` bounds correctly against the sibling
    dicts declared in the same file."""
    pat = r"export const " + re.escape(dict_name) + r"\s*=\s*\{(.*?)\n\};"
    m = re.search(pat, text, re.DOTALL)
    if not m:
        raise AssertionError(
            f"Could not locate `export const {dict_name} = {{...}};` in "
            f"{_CONSTANTS_JS} — the file layout may have changed. Update "
            f"the regex in {__file__} or restore the expected pattern."
        )
    return m.group(1)


def _glossary_defined_keys(body: str) -> set[str]:
    """From a GLOSSARY body find every top-level `'key':` — those are
    the defined terms. Multiline match anchored at line start rejects
    quoted strings that appear INSIDE definition values."""
    return set(re.findall(r"^\s*'([^']+)'\s*:", body, re.MULTILINE))


def _tile_glossary_refs(body: str) -> set[str]:
    """From a TILE_GLOSSARY_KEYS body extract every quoted string. All
    quoted strings inside this block are glossary-key REFERENCES; the
    dict's own tile keys are unquoted identifiers (e.g. `cobblestone_nearby:`
    not `'cobblestone_nearby':`), so this rule is safe."""
    return set(re.findall(r"'([^']+)'", body))


def _check() -> tuple[set[str], set[str]]:
    """Run the coverage check. Returns (defined, referenced) for the
    __main__ block to log summary counts. Raises AssertionError with a
    pointed fix message if any reference has no definition."""
    text = _CONSTANTS_JS.read_text(encoding="utf-8")
    cleaned = _strip_line_comments(text)

    gloss_body = _extract_dict_body(cleaned, "GLOSSARY")
    tiles_body = _extract_dict_body(cleaned, "TILE_GLOSSARY_KEYS")

    defined    = _glossary_defined_keys(gloss_body)
    referenced = _tile_glossary_refs(tiles_body)

    assert defined,    f"GLOSSARY parsed as empty — regex broken? File: {_CONSTANTS_JS}"
    assert referenced, f"TILE_GLOSSARY_KEYS parsed as empty — regex broken? File: {_CONSTANTS_JS}"

    missing = referenced - defined
    assert not missing, (
        f"TILE_GLOSSARY_KEYS references {len(missing)} term(s) that have no "
        f"entry in GLOSSARY — tooltip will render '—' for each:\n  "
        + "\n  ".join(sorted(missing))
        + f"\n\nFix: add each missing key to the GLOSSARY dict in "
        + str(_CONSTANTS_JS)
        + "."
    )
    return defined, referenced


if __name__ == "__main__":
    defined, referenced = _check()

    # Orphan defined-terms (in GLOSSARY but not referenced by any tile)
    # are NON-FATAL: a term can be inline-referenced from a
    # LENS_TILE_EXPLANATIONS caveat string (e.g. `noise` explanation
    # mentions `L_DEN`) without appearing in TILE_GLOSSARY_KEYS. Log
    # for visibility so a large orphan list surfaces a cleanup opportunity,
    # but do not fail the CI job on it.
    orphans = defined - referenced
    orphan_note = ""
    if orphans:
        sample = sorted(orphans)[:6]
        orphan_note = (f" · {len(orphans)} defined-but-unreferenced "
                       f"(non-fatal): {sample}"
                       + (" …" if len(orphans) > 6 else ""))

    print(f"web_glossary_selfcheck OK — "
          f"{len(defined)} defined, {len(referenced)} referenced, "
          f"0 orphan references{orphan_note}")
