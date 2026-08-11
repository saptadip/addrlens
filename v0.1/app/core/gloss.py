"""Post-processes LLM output with a per-city German glossary. Verbatim behaviour
port of phase3/server.py:_gloss_german.

The glossary lives in the app (NOT in inference-service) per plan §7.3 — each
city has its own admin vocabulary (Berlin's Kita/Träger/Situationsansatz vs
Hamburg's HmbSchulG/Elbkinder) and inference-service stays city-agnostic.

Ship B: `gloss()` now takes the glossary from CityConfig.bilingual_glossary;
no module-level default remains.
"""


def gloss(text: str, glossary) -> str:
    """Inject '(english gloss)' on the FIRST occurrence of each known German
    admin term if the model failed to translate it. Skips terms already
    followed by a parenthetical within ~60 chars (model already glossed)."""
    for rx, english in glossary:
        m = rx.search(text)
        if not m:
            continue
        tail = text[m.end(): m.end() + 60]
        if tail.lstrip().startswith("("):
            continue  # already glossed by the model
        text = text[:m.end()] + f" ({english})" + text[m.end():]
    return text


if __name__ == "__main__":
    from app.cities.berlin import BERLIN
    g = BERLIN.bilingual_glossary
    # Asserts copied verbatim from phase3/server.py:_selfcheck.
    assert "(a non-profit or private provider)" in gloss("run by a freier Träger, using Situationsansatz", g)
    assert "(a child-led Berlin pedagogy)" in gloss("run by a freier Träger, using Situationsansatz", g)
    assert "(a child-led Berlin pedagogy)" in gloss("uses the Situationssatz approach", g)  # misspelling caught
    assert "26 Kitas (daycare) within" in gloss("26 Kitas within a walk", g)
    # If the model already glossed it, don't double-gloss.
    assert gloss("freier Träger (already glossed)", g) == "freier Träger (already glossed)"
    # Empty glossary is a no-op.
    assert gloss("Träger something", []) == "Träger something"
    print("gloss.py selfcheck OK")
