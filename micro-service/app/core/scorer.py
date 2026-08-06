"""Traffic-light noise tier + rule-based stroller score. Verbatim from phase3/server.py.

The JS mirror in web/index.html MUST match stroller_score — the asserts in
__main__ are the reference set. Selfcheck asserts are the exact ones from
phase3/server.py:_selfcheck.
"""


def noise_tier(l_den_total):
    """WHO + EU-CNOSSOS action-plan thresholds → traffic-light tier for L_DEN (dB)."""
    if l_den_total is None: return "unknown"
    if l_den_total < 55:  return "green"      # WHO recommendation
    if l_den_total < 65:  return "amber"
    if l_den_total < 70:  return "orange"     # EU action-plan trigger
    return "red"


def stroller_score(floor, lift, kinderwagenraum, nearest_playground_m):
    """Rule-based livability score for a flat with a toddler + stroller.
    Inputs: floor (0=ground), lift/kinderwagenraum booleans, nearest playground
    in metres (from amenities). Returns {tier: green|amber|red|unknown, reasons}.
    The JS mirror in index.html MUST match — selfcheck below is the reference."""
    reasons = []
    if floor is None or lift is None:
        return {"tier": "unknown", "reasons": [{"kind": "info",
                "text": "Enter floor and lift to score."}]}

    # Vertical access — the daily grind that defines the tier.
    tier = "green"
    if lift:
        reasons.append({"kind": "good", "text": f"Floor {floor} with lift — carry solved."})
    elif floor == 0:
        reasons.append({"kind": "good", "text": "Ground floor — no stairs (verify no entrance step)."})
    elif floor <= 2:
        tier = "amber"
        reasons.append({"kind": "warn",
                        "text": f"Floor {floor} without lift — manageable but tiring daily."})
    else:
        tier = "red"
        reasons.append({"kind": "bad",
                        "text": f"Floor {floor} without lift — a hard no with a toddler."})

    # Kinderwagenraum — cuts the vertical problem entirely.
    if kinderwagenraum:
        reasons.append({"kind": "good",
                        "text": "Kinderwagenraum — leave the stroller downstairs."})
        if tier == "amber": tier = "green"     # upgrade
        elif tier == "red": tier = "amber"     # partial rescue

    # Playground proximity — from amenities, not a separate input.
    if nearest_playground_m is None:
        reasons.append({"kind": "info", "text": "Playground data not loaded."})
    elif nearest_playground_m < 400:
        reasons.append({"kind": "good",
                        "text": f"Playground {nearest_playground_m} m away — under 5 min walk."})
    elif nearest_playground_m < 800:
        reasons.append({"kind": "info",
                        "text": f"Nearest playground {nearest_playground_m} m — about 10 min walk."})
    else:
        reasons.append({"kind": "warn",
                        "text": "No playground within 800 m."})
        if tier == "green": tier = "amber"     # downgrade

    return {"tier": tier, "reasons": reasons}


if __name__ == "__main__":
    # noise_tier — thresholds copied verbatim from phase3/server.py:_selfcheck.
    assert noise_tier(50)   == "green"
    assert noise_tier(60)   == "amber"
    assert noise_tier(68)   == "orange"
    assert noise_tier(75)   == "red"
    assert noise_tier(None) == "unknown"

    # stroller_score — rule-based, must stay in sync with the JS mirror.
    assert stroller_score(None, True, False, 300)["tier"] == "unknown"
    assert stroller_score(0, False, False, 300)["tier"] == "green"           # ground, no lift, playground close
    assert stroller_score(3, True,  False, 300)["tier"] == "green"           # any floor with lift
    assert stroller_score(2, False, False, 300)["tier"] == "amber"           # 2nd floor, no lift
    assert stroller_score(4, False, False, 300)["tier"] == "red"             # 4th floor walk-up
    assert stroller_score(4, False, True,  300)["tier"] == "amber", \
        "Kinderwagenraum should rescue a 4th-floor walk-up from red to amber"
    assert stroller_score(2, False, True,  300)["tier"] == "green", \
        "Kinderwagenraum should lift a 2nd-floor walk-up from amber to green"
    assert stroller_score(0, True, False, 1200)["tier"] == "amber", \
        "no playground within 800m should downgrade an otherwise green flat"
    r = stroller_score(3, False, False, 300)
    assert any("hard no" in x["text"] for x in r["reasons"])
    print("scorer.py selfcheck OK")
