"""Traffic-light noise tier + rule-based stroller score. Verbatim from phase3/server.py.

The JS mirror in web/index.html MUST match stroller_score — the asserts in
__main__ are the reference set. Selfcheck asserts are the exact ones from
phase3/server.py:_selfcheck.
"""

TIER_GREEN   = "green"
TIER_AMBER   = "amber"
TIER_RED     = "red"
TIER_UNKNOWN = "unknown"


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


def _tier_kita(kitas: list, t: dict) -> dict:
    """Kita reachability. Preloaded source (Index.kitas) → never unknown."""
    green = [k for k in kitas if k["distance_m"] <= t["green_m"]]
    amber = [k for k in kitas if k["distance_m"] <= t["amber_m"]]
    if len(green) >= t["green_count"]:
        return {"tier": TIER_GREEN,
                "rule": f"≥{t['green_count']} kitas within {t['green_m']}m",
                "numeric": f"{len(green)} within {t['green_m']}m · "
                           f"nearest {green[0]['distance_m']}m"}
    if amber:
        return {"tier": TIER_AMBER,
                "rule": f"≥1 kita within {t['amber_m']}m",
                "numeric": f"{len(amber)} within {t['amber_m']}m · "
                           f"nearest {amber[0]['distance_m']}m"}
    return {"tier": TIER_RED,
            "rule": f"no kita within {t['amber_m']}m",
            "numeric": (f"nearest {kitas[0]['distance_m']}m"
                        if kitas else "none nearby")}


def _tier_playground(playgrounds: list, playgrounds_error: bool, t: dict) -> dict:
    """Playground within stroller walk. Unknown when the playground bucket
    both errored AND returned nothing (Overpass and BOD both failed)."""
    if playgrounds_error and not playgrounds:
        return {"tier": TIER_UNKNOWN,
                "rule": "Playground data unavailable",
                "numeric": "Overpass and BOD both failed"}
    within_green = [p for p in playgrounds if p["distance_m"] <= t["green_m"]]
    within_amber = [p for p in playgrounds if p["distance_m"] <= t["amber_m"]]
    if within_green:
        return {"tier": TIER_GREEN,
                "rule": f"≥1 playground within {t['green_m']}m",
                "numeric": f"{len(within_green)} within {t['green_m']}m · "
                           f"nearest {within_green[0]['distance_m']}m"}
    if within_amber:
        return {"tier": TIER_AMBER,
                "rule": f"playground {t['green_m']}–{t['amber_m']}m",
                "numeric": f"nearest {within_amber[0]['distance_m']}m"}
    return {"tier": TIER_RED,
            "rule": f"no playground within {t['amber_m']}m",
            "numeric": (f"nearest {playgrounds[0]['distance_m']}m"
                        if playgrounds else "none nearby")}


def _tier_pediatrician(paediatricians: list, gps_error: bool, t: dict) -> dict:
    """Paediatric doctor within walk. Expects `paediatricians` to be already
    filtered from the gps bucket and sorted ascending by distance."""
    if gps_error:
        return {"tier": TIER_UNKNOWN,
                "rule": "Pediatrician data unavailable",
                "numeric": "OSM Overpass unavailable"}
    within_green = [p for p in paediatricians if p["distance_m"] <= t["green_m"]]
    within_amber = [p for p in paediatricians if p["distance_m"] <= t["amber_m"]]
    if within_green:
        nearest = within_green[0]
        return {"tier": TIER_GREEN,
                "rule": f"≥1 paediatric within {t['green_m']}m",
                "numeric": (f"{len(within_green)} within {t['green_m']}m · "
                            f"nearest {nearest['distance_m']}m "
                            f"({nearest.get('name', 'unnamed')})")}
    if within_amber:
        nearest = within_amber[0]
        return {"tier": TIER_AMBER,
                "rule": f"paediatric {t['green_m']}–{t['amber_m']}m",
                "numeric": (f"nearest {nearest['distance_m']}m "
                            f"({nearest.get('name', 'unnamed')})")}
    return {"tier": TIER_RED,
            "rule": f"no paediatric within {t['amber_m']}m",
            "numeric": (f"nearest {paediatricians[0]['distance_m']}m"
                        if paediatricians else "none nearby")}


def _tier_noise(noise: dict, t: dict) -> dict:
    """Façade L_DEN. Boundary: ≤ green_db is green (inclusive)."""
    if not noise or noise.get("unavailable"):
        return {"tier": TIER_UNKNOWN,
                "rule": "Noise data unavailable",
                "numeric": (noise or {}).get("error") or "façade noise WFS down"}
    l_den = ((noise.get("l_den") or {}).get("total"))
    if l_den is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Noise data unavailable",
                "numeric": "no L_DEN reading at this façade"}
    if l_den <= t["green_db"]:
        return {"tier": TIER_GREEN,
                "rule": f"L_DEN ≤ {t['green_db']} dB",
                "numeric": f"{l_den} dB L_DEN"}
    if l_den <= t["amber_db"]:
        return {"tier": TIER_AMBER,
                "rule": f"{t['green_db']}–{t['amber_db']} dB",
                "numeric": f"{l_den} dB L_DEN"}
    return {"tier": TIER_RED,
            "rule": f"L_DEN > {t['amber_db']} dB",
            "numeric": f"{l_den} dB L_DEN"}


def _tier_heat(heat: dict, t: dict) -> dict:
    """Summer-heat class string membership. `day_class` may carry a numeric
    prefix like "> 33 °C - <= 35 °C - mäßige Belastung" (real Umweltatlas
    format) or be a bare class label like "mäßige Belastung" (test input).
    The burden class is extracted by `split(" - ")[-1].strip()`, then compared
    case-insensitively by exact equality against the config's green_classes /
    amber_classes tuples. Exact match avoids the "starke Belastung" ⊂ "sehr
    starke Belastung" ambiguity that a substring approach would create."""
    if not heat or heat.get("unavailable"):
        return {"tier": TIER_UNKNOWN,
                "rule": "Heat data unavailable",
                "numeric": (heat or {}).get("error") or "Umweltatlas WFS down"}
    day = (heat.get("day_class") or "").strip()
    if not day:
        return {"tier": TIER_UNKNOWN,
                "rule": "Heat data unavailable",
                "numeric": "no day_class on this block"}
    # Strip optional "<temp range> - " prefix; bare strings are unchanged.
    burden_class = day.split(" - ")[-1].strip()
    burden_low = burden_class.lower()
    if any(burden_low == g.lower() for g in t["green_classes"]):
        return {"tier": TIER_GREEN, "rule": "keine / geringe Belastung",
                "numeric": day}
    if any(burden_low == a.lower() for a in t["amber_classes"]):
        return {"tier": TIER_AMBER, "rule": "mäßige / starke Belastung",
                "numeric": day}
    return {"tier": TIER_RED, "rule": "sehr starke / extreme Belastung",
            "numeric": day}


def _tier_air(air: dict, t: dict) -> dict:
    """NO₂ tier. Boundary: ≤ green_ugm3 is green (inclusive)."""
    if not air or air.get("unavailable"):
        return {"tier": TIER_UNKNOWN,
                "rule": "Air-quality data unavailable",
                "numeric": (air or {}).get("error") or "Umweltatlas WFS down"}
    no2 = air.get("no2_ugm3")
    if no2 is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Air-quality data unavailable",
                "numeric": "no NO₂ reading on this segment"}
    if no2 <= t["green_ugm3"]:
        return {"tier": TIER_GREEN,
                "rule": f"NO₂ ≤ {t['green_ugm3']} μg/m³",
                "numeric": f"{no2} μg/m³ NO₂"}
    if no2 <= t["amber_ugm3"]:
        return {"tier": TIER_AMBER,
                "rule": f"NO₂ {t['green_ugm3']}–{t['amber_ugm3']} μg/m³",
                "numeric": f"{no2} μg/m³ NO₂"}
    return {"tier": TIER_RED,
            "rule": f"NO₂ > {t['amber_ugm3']} μg/m³",
            "numeric": f"{no2} μg/m³ NO₂"}


def _tier_refuge(quiet_zone: dict, trees: dict, t: dict) -> dict:
    """Composite: quiet zone distance OR tree crown coverage %. OR-forgiving
    at both tiers — losing one signal still yields a real tier. Only unknown
    when BOTH signals are missing."""
    q_m   = (quiet_zone or {}).get("distance_m")
    crown = (trees or {}).get("crown_coverage_pct")
    if q_m is None and crown is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Refuge data unavailable",
                "numeric": "quiet-zone + trees both unavailable"}
    def _parts():
        p = []
        if q_m is not None:
            name = (quiet_zone or {}).get("name") or "quiet zone"
            p.append(f"{name} at {q_m}m")
        if crown is not None:
            p.append(f"{crown}% crown")
        return " · ".join(p)

    green_hit = ((q_m is not None and q_m <= t["green_quiet_m"]) or
                 (crown is not None and crown >= t["green_crown_pct"]))
    if green_hit:
        return {"tier": TIER_GREEN,
                "rule": (f"quiet ≤ {t['green_quiet_m']}m OR "
                         f"crown ≥ {t['green_crown_pct']}%"),
                "numeric": _parts()}
    amber_hit = ((q_m is not None and q_m <= t["amber_quiet_m"]) or
                 (crown is not None and crown >= t["amber_crown_pct"]))
    if amber_hit:
        return {"tier": TIER_AMBER,
                "rule": (f"quiet ≤ {t['amber_quiet_m']}m OR "
                         f"crown ≥ {t['amber_crown_pct']}%"),
                "numeric": _parts()}
    return {"tier": TIER_RED,
            "rule": "no quiet zone within walk AND low tree cover",
            "numeric": _parts() or "no signal"}


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

    # -- Young Family lens: boundary sweeps (Spec A pure selfcheck) ----------
    from app.cities.berlin import BERLIN as _CFG_YF
    _T = {t.key: t.thresholds for t in _CFG_YF.young_family_lens.tiles}

    # Kita — inclusive on greener side.
    at_400 = [{"distance_m": 400}, {"distance_m": 350}, {"distance_m": 100}]
    at_401 = [{"distance_m": 401}, {"distance_m": 402}, {"distance_m": 403}]
    assert _tier_kita(at_400, _T["kita"])["tier"] == TIER_GREEN
    assert _tier_kita(at_401, _T["kita"])["tier"] == TIER_AMBER
    assert _tier_kita([{"distance_m": 800}], _T["kita"])["tier"] == TIER_AMBER
    assert _tier_kita([{"distance_m": 801}], _T["kita"])["tier"] == TIER_RED
    assert _tier_kita([], _T["kita"])["tier"] == TIER_RED

    # Playground.
    assert _tier_playground([{"distance_m": 400}], False, _T["playground"])["tier"] == TIER_GREEN
    assert _tier_playground([{"distance_m": 401}], False, _T["playground"])["tier"] == TIER_AMBER
    assert _tier_playground([{"distance_m": 801}], False, _T["playground"])["tier"] == TIER_RED
    assert _tier_playground([], True, _T["playground"])["tier"] == TIER_UNKNOWN

    # Pediatrician.
    P800 = [{"distance_m": 800, "name": "Dr. X"}]
    P801 = [{"distance_m": 801, "name": "Dr. Y"}]
    P1500 = [{"distance_m": 1500, "name": "Dr. Z"}]
    P1501 = [{"distance_m": 1501, "name": "Dr. W"}]
    assert _tier_pediatrician(P800, False, _T["pediatrician"])["tier"] == TIER_GREEN
    assert _tier_pediatrician(P801, False, _T["pediatrician"])["tier"] == TIER_AMBER
    assert _tier_pediatrician(P1500, False, _T["pediatrician"])["tier"] == TIER_AMBER
    assert _tier_pediatrician(P1501, False, _T["pediatrician"])["tier"] == TIER_RED
    assert _tier_pediatrician([], True, _T["pediatrician"])["tier"] == TIER_UNKNOWN

    # Noise — inclusive on greener side (55 is green, 55.01 is amber).
    assert _tier_noise({"l_den": {"total": 55}}, _T["noise"])["tier"] == TIER_GREEN
    assert _tier_noise({"l_den": {"total": 55.01}}, _T["noise"])["tier"] == TIER_AMBER
    assert _tier_noise({"l_den": {"total": 60}}, _T["noise"])["tier"] == TIER_AMBER
    assert _tier_noise({"l_den": {"total": 60.01}}, _T["noise"])["tier"] == TIER_RED
    assert _tier_noise({"unavailable": True}, _T["noise"])["tier"] == TIER_UNKNOWN

    # Heat — bare class labels (no prefix).
    assert _tier_heat({"day_class": "geringe Belastung"}, _T["heat"])["tier"] == TIER_GREEN
    assert _tier_heat({"day_class": "starke Belastung"}, _T["heat"])["tier"] == TIER_AMBER
    assert _tier_heat({"day_class": "sehr starke Belastung"}, _T["heat"])["tier"] == TIER_RED
    assert _tier_heat({"day_class": "extreme Belastung"}, _T["heat"])["tier"] == TIER_RED
    assert _tier_heat({"unavailable": True}, _T["heat"])["tier"] == TIER_UNKNOWN

    # Heat — real Umweltatlas prefix format ("<temp range> - <class>").
    assert _tier_heat({"day_class": "> 33 °C - <= 35 °C - mäßige Belastung"}, _T["heat"])["tier"] == TIER_AMBER
    assert _tier_heat({"day_class": "<= 33 °C - geringe Belastung"}, _T["heat"])["tier"] == TIER_GREEN
    assert _tier_heat({"day_class": "> 35 °C - sehr starke Belastung"}, _T["heat"])["tier"] == TIER_RED

    # Air — inclusive on greener side.
    assert _tier_air({"no2_ugm3": 20}, _T["air"])["tier"] == TIER_GREEN
    assert _tier_air({"no2_ugm3": 20.01}, _T["air"])["tier"] == TIER_AMBER
    assert _tier_air({"no2_ugm3": 40}, _T["air"])["tier"] == TIER_AMBER
    assert _tier_air({"no2_ugm3": 40.01}, _T["air"])["tier"] == TIER_RED
    assert _tier_air({"unavailable": True}, _T["air"])["tier"] == TIER_UNKNOWN

    # Refuge — composite OR.
    assert _tier_refuge({"distance_m": 400, "name": "Volkspark"},
                        {"crown_coverage_pct": 5},
                        _T["refuge"])["tier"] == TIER_GREEN  # quiet clears green
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 25},
                        _T["refuge"])["tier"] == TIER_GREEN  # crown clears green
    assert _tier_refuge({"distance_m": 1000},
                        {"crown_coverage_pct": 14.99},
                        _T["refuge"])["tier"] == TIER_AMBER  # quiet clears amber only
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 14.99},
                        _T["refuge"])["tier"] == TIER_RED
    assert _tier_refuge(None, None, _T["refuge"])["tier"] == TIER_UNKNOWN
    print("scorer.py: young_family tier boundary sweeps OK")
