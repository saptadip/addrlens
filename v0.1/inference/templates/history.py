"""`history` template — one-paragraph Berlin neighbourhood history from OSM
historic=* features within ~500 m of an address.

Response schema (§7.3.2): { "history": "<one paragraph, 60–90 words>" }.

Design notes
------------
- English only. No German words unless proper names.
- Stolpersteine are Holocaust memorials — handle with respect, never as
  'fun facts'. Cite name + fate when the payload carries them.
- Only mention facts present in the JSON — no invention (temp 0.4, low).
- End with one sentence anchoring the reader in the present.
"""
from __future__ import annotations

import json

# Lower than explain: factual, no invention allowed. History-around-a-flat
# is not a place for creative language.
SAMPLER = {
    "temp": 0.4,
    "top_p": 0.9,
    "repetition_penalty": 1.15,
    "max_tokens": 260,
}

_SYSTEM = (
    "You are a Berlin neighbourhood historian writing for an English-speaking "
    "expat who is considering moving to this area. You receive a JSON "
    "list of historic points of interest within ~500 metres: "
    "memorials, monuments, plaques, ruins, old rail lines, listed buildings. "
    "Weave the most notable 2–4 items into ONE short paragraph, 60–90 words. "
    "Ground rules: "
    "(1) English only. Do not use German words unless they are proper names "
    "(borough names and 'Stolperstein' — which is fine, other German is not). "
    "(2) Stolpersteine are pavement brass plaques marking the last freely-chosen "
    "home of a person deported by the Nazis. Handle with respect: state the "
    "person's name and fate when the payload has them; never call them 'fun "
    "facts' or 'landmarks'. "
    "(3) Only mention facts present in the JSON — never invent dates, names, "
    "or context. If a field is missing, skip it. "
    "(4) Do not editorialise about property values or 'good/bad neighbourhoods'. "
    "(5) Refer to the location as 'this block', 'the neighbourhood', or the "
    "borough / Ortsteil name from the header. NEVER mention a specific street "
    "name or house number — the paragraph is reused for every address on the "
    "block, so a street-specific opener would be wrong for the neighbours. "
    "(6) End with one sentence anchoring the reader in the present — what the "
    "visitor will physically see when they walk past. "
    "Return only the paragraph. No headings, no bullet lists, no preamble."
)


def build_messages(context: dict) -> list[dict]:
    feats = context.get("features") or []
    if not isinstance(feats, list):
        raise ValueError("context.features must be a list")
    # Cap at 5 features to keep the prompt tight — the model does better
    # weaving 2-4 items than triaging 20. Assumes upstream sorted by distance.
    shown = feats[:5]
    # Header carries only borough / Ortsteil — never a specific street or
    # house number. The narrative is cached per ~100 m grid cell (see
    # app/routes/history.py) and reused for every address in the cell, so
    # an address-specific opener like "Buschallee 3" would be wrong for the
    # next-door neighbour who hits the same cache entry.
    header = (
        f"Neighbourhood: {context.get('bezirk','?')}, "
        f"{context.get('ortsteil','?')} (Berlin)"
    )
    facts = json.dumps(shown, ensure_ascii=False, indent=2)[:2400]
    return [
        {"role": "system", "content": _SYSTEM},
        # One-shot pattern to lock in the tone. Stolperstein handling is the
        # key thing to demonstrate; the assistant reply teaches respect + form.
        # Opener is intentionally address-agnostic ("On this block", not
        # "Outside the front door of 40 Choriner Straße") so the model learns
        # to produce cache-shareable prose.
        {"role": "user", "content":
            "Neighbourhood: Pankow, Prenzlauer Berg (Berlin)\n\n"
            "Historic points within 500 m (3 total, top 3 by proximity):\n"
            "[{\"distance_m\":40,\"historic\":\"memorial\",\"name\":\"Anna Winter\","
            "\"inscription\":\"Hier wohnte Anna Winter, Jg. 1889, deportiert 1942, "
            "ermordet in Riga\"},"
            "{\"distance_m\":180,\"historic\":\"monument\",\"name\":\"Fallen Wall marker\","
            "\"inscription\":\"\"},"
            "{\"distance_m\":320,\"historic\":\"building\",\"name\":\"Kulturbrauerei\","
            "\"wikipedia\":\"de:Kulturbrauerei\"}]"},
        {"role": "assistant", "content":
            "On this block a Stolperstein commemorates Anna Winter, born 1889 and "
            "deported in 1942 before being murdered in Riga — the small brass plaque set into the "
            "pavement is the last freely-chosen address she left. A short walk away, a marker records "
            "the line of the former Wall, and 300 metres to the south the red-brick "
            "Kulturbrauerei — a 19th-century brewery turned arts complex — anchors local "
            "cultural life. Walk slowly through the neighbourhood and watch the pavement."},
        {"role": "user", "content": f"{header}\n\nHistoric points within 500 m ({len(feats)} total, top {len(shown)} by proximity):\n{facts}"},
    ]


def run(backend, context: dict) -> dict:
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if not context.get("features"):
        return {"history": "No historic points on record within 500 m of this address."}
    msgs = build_messages(context)
    text = backend.generate_from_messages(msgs, **SAMPLER)
    return {"history": text}


if __name__ == "__main__":
    # Prompt shape asserts — matches explain.py style. Runs offline, no model.
    msgs = build_messages({
        "bezirk":   "Lichtenberg",
        "ortsteil": "Alt-Hohenschönhausen",
        "features": [
            {"distance_m": 93, "historic": "memorial", "name": "Fritz Leyser",
             "inscription": "Hier wohnte Fritz Leyser, Jg. 1896, deportiert 9.12.1942, ermordet in Auschwitz"},
        ],
    })
    assert msgs[0]["role"] == "system"
    assert "Stolperstein" in msgs[0]["content"]
    assert "Fritz Leyser" in msgs[-1]["content"]
    # Header must NOT leak a street name or house number — the paragraph is
    # cache-shared across a ~100 m cell, so anything address-specific breaks
    # correctness for neighbouring addresses.
    _final_user = msgs[-1]["content"]
    assert "Address:" not in _final_user, "header must not include street/hnr"
    assert "Neighbourhood:" in _final_user, "header must be borough / Ortsteil scoped"
    # System prompt must forbid street-specific openers.
    _sys = msgs[0]["content"].lower()
    assert "never mention a specific street" in _sys, \
        "system must forbid street-specific mentions for cache safety"
    # Assistant one-shot must model respectful Stolperstein handling AND
    # the address-agnostic opener.
    _asst = next(m["content"] for m in msgs if m["role"] == "assistant")
    assert "Stolperstein" in _asst
    assert "Choriner" not in _asst, \
        "one-shot exemplar must not mention a specific street name"
    # Anti-invention: system must forbid inventing facts.
    assert "never invent" in msgs[0]["content"].lower() or "no invention" in msgs[0]["content"].lower()
    # Empty features shortcut.
    empty = run(None, {"features": []})
    assert "No historic" in empty["history"]
    print("history.py selfcheck OK")
