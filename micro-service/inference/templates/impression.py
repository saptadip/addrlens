"""`impression` template — mode-branched few-shot for a family's neighborhood
impression per tab. Verbatim messages from phase3/server.py:_build_impression_messages.

Anti-inversion behaviour ("no Kaufland nearby" stays "no Kaufland nearby") is
guaranteed by both the system prompt and the negative/mixed few-shot examples.
Any change here must preserve that — it's the Ship LLM-1 exit criterion.
"""
from __future__ import annotations

# Sampler settings — tuned in phase3 to minimise invention/inversion.
SAMPLER = {
    "temp": 0.6,
    "top_p": 0.9,
    "repetition_penalty": 1.25,
    "max_tokens": 110,
}


def build_messages(mode, tab, address, happy, sad, sad_details=None):
    """Sentiment-matched system + few-shot. Small model can't reliably invent
    from nothing; every mode has an assistant example demonstrating the
    expected shape and tone for that exact sentiment.

    sad_details: {category_label: "chip, chip, \"free text\""} — user's own
    words on why the 👎 landed. Woven into negative + mixed prompts so the
    1.5B model has structured concern signal, not just a category name."""
    liked    = ", ".join(happy)
    disliked = ", ".join(sad)
    sd = sad_details or {}
    concerns_block = ("\nSpecific concerns:\n" +
                      "\n".join(f"  - {cat}: {reason}" for cat, reason in sd.items())) if sd else ""
    if mode == "mixed":
        return [
            {"role": "system", "content":
                "You're a friendly Berliner giving a family your honest take on their new neighborhood, "
                "based on things they liked and things that bothered them nearby. "
                "'Specific concerns' are the family's own complaints — echo them faithfully. "
                "NEVER invert a negation: if they say 'no Kaufland nearby' you must say 'no Kaufland nearby', "
                "NOT 'only one Kaufland nearby'. NEVER spin a complaint into a positive. "
                "Two short sentences, warm and specific. Speak to them as \"you\". No lists, no headings."},
            {"role": "user", "content":
                "Category: amenities. Address: Danziger Str. 44, 10405.\n"
                "Liked: Playgrounds, Parks.\n"
                "Bothered: Supermarkets.\n"
                "Specific concerns:\n  - Supermarkets: Too far, Discount-only, \"no Rewe nearby\""},
            {"role": "assistant", "content":
                "You've landed on a proper family Kiez — the playgrounds and parks are why locals fight "
                "to stay here. The supermarket run is the catch: it's a hike, mostly discount stores, and "
                "no Rewe nearby, so plan the weekly shop around an Edeka on the S-Bahn."},
            {"role": "user", "content":
                f"Category: {tab}. Address: {address}.\nLiked: {liked}.\nBothered: {disliked}.{concerns_block}"},
        ]
    if mode == "positive":
        return [
            {"role": "system", "content":
                "You're a friendly Berliner. A family loved EVERYTHING nearby in this category — "
                "every single amenity got a thumbs-up. Write two warm sentences celebrating the fit. "
                "Weave in the specific place types they liked. Speak to them as \"you\". No lists."},
            {"role": "user", "content":
                "Category: amenities. Address: Kollwitzstr 66, 10435.\n"
                "The family loved everything nearby: Playgrounds, Parks, Drinking fountains.\n"},
            {"role": "assistant", "content":
                "You've hit the family Kiez jackpot — the playgrounds and parks around here are why "
                "locals with strollers never seem to leave. Add the drinking fountains for the summer "
                "heat and you've got a neighborhood that quietly does the work of raising kids for you."},
            {"role": "user", "content":
                f"Category: {tab}. Address: {address}.\n"
                f"The family loved everything nearby: {liked}.\n"},
        ]
    # negative
    return [
        {"role": "system", "content":
            "You're a friendly Berliner giving a family an honest reality check. They gave a "
            "thumbs-DOWN to EVERY amenity nearby in this category — nothing worked for them. "
            "'Specific concerns' are the family's own complaints — echo them faithfully. "
            "NEVER invert a negation: if they say 'no Kaufland nearby' you must say 'no Kaufland nearby', "
            "NOT 'only one Kaufland nearby'. NEVER spin a complaint into a positive. "
            "Do NOT claim things are good, do NOT invent positives. Write two honest sentences "
            "acknowledging the frustration and suggesting a practical workaround. Speak to them "
            "as \"you\". No lists, no headings."},
        {"role": "user", "content":
            "Category: medical. Address: Buschkrugallee 90, 12359.\n"
            "The family was unhappy with everything nearby: Pharmacies, Doctors, Hospitals.\n"
            "Specific concerns:\n  - Doctors: Not accepting patients, No English, \"no pediatrician takes us\"\n  - Hospitals: Too far"},
        {"role": "assistant", "content":
            "You've spotted a real weak point of this Kiez — the doctors nearby aren't taking new patients, "
            "few speak English, no pediatrician takes you, and the hospitals are a haul. Plan on registering "
            "with a Hausarzt closer to work, and keep the S-Bahn map handy for hospital runs."},
        {"role": "user", "content":
            f"Category: {tab}. Address: {address}.\n"
            f"The family was unhappy with everything nearby: {disliked}.{concerns_block}"},
    ]


def run(backend, context: dict) -> dict:
    """Iterate votes per tab, generate one summary per tab with content.
    Returns {tab: text}. Empty tabs (no happy/sad) are skipped, matching phase3."""
    address = context.get("address") or "this address"
    votes = context.get("votes") or {}
    out = {}
    for tab, cats in votes.items():
        happy = cats.get("happy") or []
        sad   = cats.get("sad") or []
        sad_details = cats.get("sad_details") or {}
        if not happy and not sad:
            continue
        if happy and sad: mode = "mixed"
        elif happy:       mode = "positive"
        else:             mode = "negative"
        msgs = build_messages(mode, tab, address, happy, sad, sad_details)
        out[tab] = backend.generate_from_messages(msgs, **SAMPLER)
    return out


if __name__ == "__main__":
    # Anti-inversion asserts copied verbatim from phase3/server.py:_selfcheck.
    msgs = build_messages("negative", "amenities", "Addr", [], ["Supermarkets"],
                          {"Supermarkets": "Too far, Discount-only"})
    assert "Too far, Discount-only" in msgs[-1]["content"]
    msgs = build_messages("mixed", "amenities", "Addr", ["Parks"], ["Supermarkets"],
                          {"Supermarkets": "Limited choice"})
    assert "Limited choice" in msgs[-1]["content"]
    msgs = build_messages("negative", "amenities", "Addr", [], ["Supermarkets"], None)
    assert "Specific concerns" not in msgs[-1]["content"]
    print("impression.py selfcheck OK")
