"""Pure tier functions — feature list + thresholds → `{tier, rule, numeric}`.

Also hosts two shared helpers introduced in Ship D step 2:

- `_tier_distance_ladder(features, th, *, nearest_label, empty_label, numeric_prefix)`
  collapses eight near-identical distance-band tier funcs (buergeramt
  newcomer, tram / bus / english_clinic / language_school / library /
  packstation / wochenmarkt). Byte-exact output preservation vs. the
  previous per-tile implementations.

- `_tier_count_band(features, th, *, rule_label, numeric_fmt)` collapses
  the two count-band tiers (`intl_food`, `coworking`). Numeric string
  differs between the two, so it's passed as a callable.

Kept as thin wrappers so the load-bearing scorer selfcheck and other
call sites keep referencing the same names.
"""

from typing import Optional

from app.core.scoring.constants import (
    TIER_AMBER, TIER_GREEN, TIER_RED, TIER_UNKNOWN, _fmt_dist,
)


# ==================================================================== #
# Shared helpers — collapsed distance-ladder + count-band tiers.       #
# ==================================================================== #


def _tier_distance_ladder(features: list, th: dict, *,
                          nearest_label: str,
                          empty_label: str,
                          numeric_prefix: str = "") -> dict:
    """Distance-to-nearest ladder shared by 8 Newcomer tiles.

    Green iff ``nearest.distance_m <= th['green_m']``; else amber iff
    ``<= th['amber_m']``; else red. Empty features → red with numeric="".

    - `nearest_label`: goes into green/amber rule text ("Bürgeramt",
      "tram stop", "bus stop", "English clinic", "German school",
      "library", "Packstation", "Wochenmarkt").
    - `empty_label`:   goes into the "no {…} within {r}" rule text.
      Usually the same as `nearest_label`, except transit tiles use
      "tram"/"bus" (not "tram stop"/"bus stop").
    - `numeric_prefix`: prefix on the feature name in the numeric string
      ("Tram ", "Bus ", ""). Preserves the historical distinction
      between transit and non-transit numeric strings.
    """
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no {empty_label} within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"{nearest_label} ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"{nearest_label} ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no {empty_label} within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to {numeric_prefix}{nearest['name']}"}


def _tier_count_band(features: list, th: dict, *,
                     rule_label: str,
                     numeric_fmt) -> dict:
    """Count-in-radius band shared by 2 Newcomer tiles.

    - green iff ``len(features) >= th['green_count']``
    - amber iff ``>= th['amber_count']``
    - else red

    `numeric_fmt(n, radius_m) -> str` — because `intl_food` and
    `coworking` build subtly different numeric strings ("international
    spots within N m walk" vs "remote-work spots within N m").
    """
    n = len(features)
    r = _fmt_dist(th['radius_m'])
    if n >= th["green_count"]:
        tier = TIER_GREEN
        rule = f"≥{th['green_count']} {rule_label} within {r}"
    elif n >= th["amber_count"]:
        tier = TIER_AMBER
        rule = f"{th['amber_count']}–{th['green_count']-1} {rule_label} within {r}"
    else:
        tier = TIER_RED
        rule = f"<{th['amber_count']} {rule_label} within {r}"
    return {"tier": tier, "rule": rule, "numeric": numeric_fmt(n, th['radius_m'])}


# ==================================================================== #
# Standalone tiers used across the app.                                #
# ==================================================================== #


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

    if kinderwagenraum:
        reasons.append({"kind": "good",
                        "text": "Kinderwagenraum — leave the stroller downstairs."})
        if tier == "amber": tier = "green"
        elif tier == "red": tier = "amber"

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
        if tier == "green": tier = "amber"

    return {"tier": tier, "reasons": reasons}


# ==================================================================== #
# Young Family tiers.                                                  #
# ==================================================================== #


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
    """Summer-heat class string membership."""
    if not heat or heat.get("unavailable"):
        return {"tier": TIER_UNKNOWN,
                "rule": "Heat data unavailable",
                "numeric": (heat or {}).get("error") or "Umweltatlas WFS down"}
    day = (heat.get("day_class") or "").strip()
    if not day:
        return {"tier": TIER_UNKNOWN,
                "rule": "Heat data unavailable",
                "numeric": "no day_class on this block"}
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
    """Composite: quiet zone distance OR tree crown coverage %."""
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


def _tier_from_walk(walk_min: Optional[int], green_min: int, amber_min: int) -> str:
    """Generic proximity → tier. Used for transit + supermarket YF tiles.
    ≤ green_min = green; ≤ amber_min = amber; else red; None = unknown."""
    if walk_min is None:
        return TIER_UNKNOWN
    if walk_min <= green_min:
        return TIER_GREEN
    if walk_min <= amber_min:
        return TIER_AMBER
    return TIER_RED


def _tier_transit(features: list, t: dict) -> dict:
    """YF Transit tile — 'is ≥1 public-transport stop reachable with a
    stroller?' Features is the shaped list of nearest-per-modality stops."""
    if not features:
        return {"tier": TIER_UNKNOWN,
                "rule": "Transit data unavailable",
                "numeric": "no transit stops loaded"}
    nearest = min(features, key=lambda f: f.get("walk_min", 10**9))
    walk = nearest.get("walk_min")
    tier = _tier_from_walk(walk, t["green_min"], t["amber_min"])
    modes = " · ".join(dict.fromkeys(f.get("modality", "") for f in features if f.get("modality")))
    if tier == TIER_GREEN:
        rule = f"≥1 stop within {t['green_min']} min stroller walk"
    elif tier == TIER_AMBER:
        rule = f"nearest stop {t['green_min']}–{t['amber_min']} min walk"
    else:
        rule = f"no stop within {t['amber_min']} min walk"
    return {"tier": tier, "rule": rule,
            "numeric": f"nearest {nearest['name']} ({nearest.get('modality','?')}) — ~{walk} min · {modes}"}


def _tier_gesix(g: dict) -> dict:
    """Neighbourhood health & social composite (Berlin Senate GESIx 2022).
    g is the dict returned by Index.gesix_at, or None."""
    if not g or g.get("quintile_5") is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Neighbourhood profile unavailable",
                "numeric": "no GESIx polygon covers this address"}
    q = g["quintile_5"]
    plr = g.get("plr_name") or "Unnamed Planungsraum"
    rang = g.get("rang")
    total = g.get("total") or 447
    if q <= 2:
        tier = TIER_GREEN
        rule = "Top two quintiles citywide (health + social composite)"
    elif q == 3:
        tier = TIER_AMBER
        rule = "Middle quintile citywide (health + social composite)"
    else:
        tier = TIER_RED
        rule = "Bottom two quintiles citywide (health + social composite)"
    numeric = f"{plr} — quintile {q} of 5 · rank {rang}/{total}"
    return {"tier": tier, "rule": rule, "numeric": numeric}


def _tier_supermarket(features: list, t: dict) -> dict:
    """YF Supermarket tile — 'grocery run within stroller walk'."""
    within_green = [f for f in features if (f.get("walk_min") or 10**9) <= t["green_min"]]
    within_amber = [f for f in features if (f.get("walk_min") or 10**9) <= t["amber_min"]]
    if within_green:
        n = within_green[0]
        return {"tier": TIER_GREEN,
                "rule": f"≥1 supermarket within {t['green_min']} min stroller walk",
                "numeric": (f"{len(within_green)} within {t['green_min']} min · "
                            f"nearest {n['name']} · ~{n['walk_min']} min")}
    if within_amber:
        n = within_amber[0]
        return {"tier": TIER_AMBER,
                "rule": f"supermarket {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"nearest {n['name']} · ~{n['walk_min']} min"}
    return {"tier": TIER_RED,
            "rule": f"no supermarket within {t['amber_min']} min walk",
            "numeric": (f"nearest {features[0]['name']} · ~{features[0]['walk_min']} min"
                        if features else "none nearby")}


# ==================================================================== #
# Newcomer tiers.                                                      #
#                                                                      #
# The 8 distance-ladder tiles all wrap `_tier_distance_ladder`; the 2  #
# count-band tiles wrap `_tier_count_band`. Wrappers are kept so the   #
# scorer regression selfcheck can call each by its historical name.    #
# ==================================================================== #


def _tier_buergeramt_newcomer(features: list, th: dict) -> dict:
    """Newcomer Bürgeramt tile — distance-to-nearest logic."""
    return _tier_distance_ladder(features, th,
                                  nearest_label="Bürgeramt",
                                  empty_label="Bürgeramt")


def _tier_rail_transit(features: list, th: dict) -> dict:
    """Newcomer Rail-Transit tile — heavy-rail (S-Bahn + U-Bahn) only.

    Dual-threshold: green if S ≤ sbahn_m OR U ≤ ubahn_m; amber if any
    S/U ≤ any_rail_m. Does not fit `_tier_distance_ladder` — kept
    as its own function.
    """
    green_rule = (f"S-Bahn ≤{_fmt_dist(th['sbahn_m'])} OR "
                  f"U-Bahn ≤{_fmt_dist(th['ubahn_m'])}")
    amber_rule = f"rail ≤{_fmt_dist(th['any_rail_m'])}"
    red_rule   = f"no rail within {_fmt_dist(th['any_rail_m'])}"
    if not features:
        return {"tier": TIER_RED, "rule": red_rule, "numeric": ""}
    for f in features:
        d = f["distance_m"]
        mode = f.get("mode", "")
        if "S" in mode and d <= th["sbahn_m"]:
            return {"tier": TIER_GREEN, "rule": green_rule,
                    "numeric": f"{int(d)} m to S-Bahn {f['name']}"}
        if "U" in mode and d <= th["ubahn_m"]:
            return {"tier": TIER_GREEN, "rule": green_rule,
                    "numeric": f"{int(d)} m to U-Bahn {f['name']}"}
    for f in features:
        if f["distance_m"] <= th["any_rail_m"]:
            mode_label = {"S": "S-Bahn", "U": "U-Bahn"}.get(
                f.get("mode", "")[:1], "Rail")
            return {"tier": TIER_AMBER, "rule": amber_rule,
                    "numeric": f"{int(f['distance_m'])} m to {mode_label} {f['name']}"}
    return {"tier": TIER_RED, "rule": red_rule, "numeric": ""}


def _tier_tram_transit(features: list, th: dict) -> dict:
    """Newcomer Tram-Transit tile — distance-to-nearest tram stop."""
    return _tier_distance_ladder(features, th,
                                  nearest_label="tram stop",
                                  empty_label="tram",
                                  numeric_prefix="Tram ")


def _tier_bus_transit(features: list, th: dict) -> dict:
    """Newcomer Bus-Transit tile — distance-to-nearest bus stop."""
    return _tier_distance_ladder(features, th,
                                  nearest_label="bus stop",
                                  empty_label="bus",
                                  numeric_prefix="Bus ")


def _tier_intl_food(features: list, th: dict) -> dict:
    """Count-based tier for international food & grocers within radius_m."""
    return _tier_count_band(features, th,
                             rule_label="intl food spots",
                             numeric_fmt=lambda n, r:
                                f"{n} international spots within {r} m walk")


def _tier_coworking(features: list, th: dict) -> dict:
    """Count-based tier for coworking spaces + Wi-Fi cafés within radius_m."""
    return _tier_count_band(features, th,
                             rule_label="coworking / laptop cafés",
                             numeric_fmt=lambda n, r:
                                f"{n} remote-work spots within {r} m")


def _tier_english_clinic(features: list, th: dict) -> dict:
    """Distance-to-nearest English-tagged medical practice.

    ponytail: OSM 'language:en=yes' tagging is community-maintained;
    inner-district coverage is good, outer Berlin may under-report.
    """
    return _tier_distance_ladder(features, th,
                                  nearest_label="English clinic",
                                  empty_label="English clinic")


def _tier_language_school(features: list, th: dict) -> dict:
    """Distance-to-nearest language school (VHS + private Sprachschulen)."""
    return _tier_distance_ladder(features, th,
                                  nearest_label="German school",
                                  empty_label="German school")


def _tier_library(features: list, th: dict) -> dict:
    """Distance-to-nearest public library (VÖBB + Uni libraries)."""
    return _tier_distance_ladder(features, th,
                                  nearest_label="library",
                                  empty_label="library")


def _tier_packstation(features: list, th: dict) -> dict:
    """Distance-to-nearest parcel pickup point (DHL + Post branch)."""
    return _tier_distance_ladder(features, th,
                                  nearest_label="Packstation",
                                  empty_label="Packstation")


def _tier_nightlife_density(features: list, th: dict) -> dict:
    """Numeric-only nightlife density tile — always tier=unknown.

    ponytail: `th` is accepted for signature parity with the other
    `_tier_*` functions but ignored — the 1 km radius is hardcoded in
    the composer's `_osm_near("nightlife", 1000)` call. Upgrade path:
    move the radius into `cfg.newcomer_lens.tiles["nightlife_density"].
    thresholds["radius_m"]` and read it here.
    """
    n = len(features)
    if n == 0:
        return {"tier": TIER_UNKNOWN,
                "rule": "no bars / clubs within 1km",
                "numeric": ""}
    return {"tier": TIER_UNKNOWN,
            "rule": f"{n} bars / clubs within 1km · numeric only",
            "numeric": f"{n} bars / clubs / pubs within 1 km"}


# ==================================================================== #
# Quiet Living tiers.                                                  #
# ==================================================================== #


def _tier_tempo30(tempo: dict, th: dict) -> dict:
    """Speed limit at the address. `tempo` is either None (no exception
    feature within radius — default 50 km/h applies) or a dict from
    `Index.tempolimit_at` with `speed_kmh`, `distance_m`, `reason`,
    `time_restriction`.

    Green if ≤ green_kmh (Tempo-30 territory), red if ≥ red_kmh
    (arterial / Stadtautobahn), amber for the default 40–50."""
    if not tempo or tempo.get("speed_kmh") is None:
        # No exception feature nearby: general 50 km/h applies. Not
        # unknown — Berlin's default IS documented public information.
        return {"tier": TIER_AMBER,
                "rule": f"default {th.get('default_kmh', 50)} km/h (no exception nearby)",
                "numeric": f"assumed {th.get('default_kmh', 50)} km/h"}
    speed = float(tempo["speed_kmh"])
    d = tempo["distance_m"]
    reason = tempo.get("reason")
    time_r = tempo.get("time_restriction")
    numeric_bits = [f"{int(speed)} km/h at {int(d)} m"]
    if time_r:
        numeric_bits.append(f"({time_r})")
    if reason:
        numeric_bits.append(f"— {reason}")
    numeric = " ".join(numeric_bits)
    if speed <= th["green_kmh"]:
        return {"tier": TIER_GREEN,
                "rule": f"speed limit ≤ {th['green_kmh']} km/h",
                "numeric": numeric}
    if speed <= th["amber_kmh"]:
        return {"tier": TIER_AMBER,
                "rule": f"speed limit {th['green_kmh']+1}–{th['amber_kmh']} km/h",
                "numeric": numeric}
    return {"tier": TIER_RED,
            "rule": f"speed limit > {th['amber_kmh']} km/h",
            "numeric": numeric}


def _tier_arterial_road(arterial: dict, th: dict) -> dict:
    """Distance to the nearest arterial road. `arterial` is None (nothing
    within the search radius = quiet residential) or a dict from
    `Index.nearest_arterial` with `name`, `class`, `distance_m`.

    Green ≥ green_m (side-street territory), red < amber_m (directly on
    or next to an arterial)."""
    if not arterial:
        return {"tier": TIER_GREEN,
                "rule": f"≥ {th['green_m']} m to nearest arterial",
                "numeric": "no arterial within search radius"}
    d = arterial["distance_m"]
    label = arterial.get("name") or "arterial road"
    if d >= th["green_m"]:
        return {"tier": TIER_GREEN,
                "rule": f"≥ {th['green_m']} m to nearest arterial",
                "numeric": f"{int(d)} m to {label}"}
    if d >= th["amber_m"]:
        return {"tier": TIER_AMBER,
                "rule": f"{th['amber_m']}–{th['green_m']-1} m to nearest arterial",
                "numeric": f"{int(d)} m to {label}"}
    return {"tier": TIER_RED,
            "rule": f"< {th['amber_m']} m to nearest arterial",
            "numeric": f"{int(d)} m to {label}"}


def _tier_rail_noise(rail: dict, th: dict) -> dict:
    """Rail-track proximity as a noise proxy. `rail` is None (no S/U
    station preloaded) or a dict from `Index.rail_track_proximity` with
    `mode`, `name`, `distance_m`.

    ponytail: uses station coordinates as a proxy for the tracks that
    generate the actual noise. Upgrade path documented on the Index
    method. U-Bahn is treated as always green because Berlin's U-Bahn
    is underground on most sections (elevated Hochbahn portions are
    the exception, not the rule).
    """
    if not rail:
        return {"tier": TIER_GREEN,
                "rule": f"no rail station within {th['amber_m']} m",
                "numeric": "no S-Bahn or U-Bahn station preloaded"}
    if rail.get("mode") == "U-Bahn":
        return {"tier": TIER_GREEN,
                "rule": "nearest rail is U-Bahn (underground on most sections)",
                "numeric": f"{int(rail['distance_m'])} m to U-Bahn {rail['name']}"}
    d = rail["distance_m"]
    name = rail.get("name", "rail")
    if d >= th["green_m"]:
        return {"tier": TIER_GREEN,
                "rule": f"S-Bahn ≥ {th['green_m']} m away",
                "numeric": f"{int(d)} m to S-Bahn {name}"}
    if d >= th["amber_m"]:
        return {"tier": TIER_AMBER,
                "rule": f"S-Bahn {th['amber_m']}–{th['green_m']-1} m away",
                "numeric": f"{int(d)} m to S-Bahn {name}"}
    return {"tier": TIER_RED,
            "rule": f"S-Bahn < {th['amber_m']} m away",
            "numeric": f"{int(d)} m to S-Bahn {name}"}


def _tier_quiet_zone_solo(quiet_zone: dict, th: dict) -> dict:
    """Standalone version of the quiet-zone distance signal — no
    compositing with trees. Threshold shape: {"green_m", "amber_m"}.
    None → unknown (WFS didn't return anything within its own radius)."""
    if not quiet_zone or quiet_zone.get("distance_m") is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Quiet-zone data unavailable",
                "numeric": "no quiet-zone polygon within search"}
    d = quiet_zone["distance_m"]
    name = (quiet_zone.get("name") or "").strip() or "quiet zone"
    if d <= th["green_m"]:
        return {"tier": TIER_GREEN,
                "rule": f"quiet zone within {th['green_m']} m",
                "numeric": f"{int(d)} m to {name}"}
    if d <= th["amber_m"]:
        return {"tier": TIER_AMBER,
                "rule": f"quiet zone within {th['amber_m']} m",
                "numeric": f"{int(d)} m to {name}"}
    return {"tier": TIER_RED,
            "rule": f"no quiet zone within {th['amber_m']} m",
            "numeric": f"{int(d)} m to {name}"}


def _tier_street_trees(trees: dict, th: dict) -> dict:
    """Street-tree canopy coverage in a bbox around the address.
    Threshold shape: {"green_pct", "amber_pct"}.
    Green ≥ green_pct, amber ≥ amber_pct."""
    if not trees or trees.get("crown_coverage_pct") is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Street-tree data unavailable",
                "numeric": (trees or {}).get("error") or "trees WFS returned no rows"}
    pct = trees["crown_coverage_pct"]
    n = trees.get("count", 0)
    numeric = f"{pct}% canopy across {n} trees"
    if pct >= th["green_pct"]:
        return {"tier": TIER_GREEN,
                "rule": f"canopy ≥ {th['green_pct']}%",
                "numeric": numeric}
    if pct >= th["amber_pct"]:
        return {"tier": TIER_AMBER,
                "rule": f"canopy {th['amber_pct']}–{th['green_pct']-1}%",
                "numeric": numeric}
    return {"tier": TIER_RED,
            "rule": f"canopy < {th['amber_pct']}%",
            "numeric": numeric}


def _tier_nightlife_inverted(features: list, th: dict) -> dict:
    """Inverted nightlife density — for the Quiet Living lens, fewer
    bars / clubs / pubs within radius is GREEN, not the newcomer
    lens's numeric-only stance. Same OSM data, opposite framing.

    Threshold shape: {"radius_m", "green_max", "amber_max"}.
    Green ≤ green_max; amber green_max+1..amber_max; red > amber_max.
    """
    n = len(features)
    r = _fmt_dist(th["radius_m"])
    numeric = f"{n} bars / clubs / pubs within {th['radius_m']} m"
    if n <= th["green_max"]:
        return {"tier": TIER_GREEN,
                "rule": f"≤ {th['green_max']} nightlife venues within {r}",
                "numeric": numeric}
    if n <= th["amber_max"]:
        return {"tier": TIER_AMBER,
                "rule": f"{th['green_max']+1}–{th['amber_max']} nightlife venues within {r}",
                "numeric": numeric}
    return {"tier": TIER_RED,
            "rule": f"> {th['amber_max']} nightlife venues within {r}",
            "numeric": numeric}


def _tier_wochenmarkt(features: list, th: dict) -> dict:
    """Distance-to-nearest permitted weekly market (Wochenmarkt).

    ponytail: OSM/BOD closure lag can be 6-12 months; a "green" tile at
    an address next to a recently-closed market will look wrong for a
    season.
    """
    return _tier_distance_ladder(features, th,
                                  nearest_label="Wochenmarkt",
                                  empty_label="Wochenmarkt")


if __name__ == "__main__":
    # noise_tier — thresholds copied verbatim from phase3.
    assert noise_tier(50) == "green"
    assert noise_tier(60) == "amber"
    assert noise_tier(68) == "orange"
    assert noise_tier(75) == "red"
    assert noise_tier(None) == "unknown"

    # stroller_score — sync w/ JS mirror.
    assert stroller_score(None, True, False, 300)["tier"] == "unknown"
    assert stroller_score(0, False, False, 300)["tier"] == "green"
    assert stroller_score(3, True, False, 300)["tier"] == "green"
    assert stroller_score(2, False, False, 300)["tier"] == "amber"
    assert stroller_score(4, False, False, 300)["tier"] == "red"
    assert stroller_score(4, False, True, 300)["tier"] == "amber"
    assert stroller_score(2, False, True, 300)["tier"] == "green"
    assert stroller_score(0, True, False, 1200)["tier"] == "amber"

    # -- Collapsed distance-ladder — byte-exact parity vs old per-tile funcs.
    th = {"green_m": 500, "amber_m": 1000}
    r = _tier_distance_ladder([{"name": "X", "distance_m": 500}], th,
                              nearest_label="tram stop", empty_label="tram",
                              numeric_prefix="Tram ")
    assert r == {"tier": "green",
                 "rule": "tram stop ≤500m walk",
                 "numeric": "500 m to Tram X"}, r
    r = _tier_distance_ladder([{"name": "X", "distance_m": 1000}], th,
                              nearest_label="tram stop", empty_label="tram",
                              numeric_prefix="Tram ")
    assert r == {"tier": "amber",
                 "rule": "tram stop ≤1km",
                 "numeric": "1000 m to Tram X"}, r
    r = _tier_distance_ladder([{"name": "X", "distance_m": 1001}], th,
                              nearest_label="tram stop", empty_label="tram",
                              numeric_prefix="Tram ")
    assert r == {"tier": "red",
                 "rule": "no tram within 1km",
                 "numeric": "1001 m to Tram X"}, r
    r = _tier_distance_ladder([], th,
                              nearest_label="tram stop", empty_label="tram",
                              numeric_prefix="Tram ")
    assert r == {"tier": "red", "rule": "no tram within 1km", "numeric": ""}, r

    # -- Collapsed count-band.
    th_c = {"radius_m": 1000, "green_count": 6, "amber_count": 2}
    r = _tier_count_band(
        [{"name": f"x{i}"} for i in range(6)], th_c,
        rule_label="intl food spots",
        numeric_fmt=lambda n, radius: f"{n} international spots within {radius} m walk",
    )
    assert r == {"tier": "green",
                 "rule": "≥6 intl food spots within 1km",
                 "numeric": "6 international spots within 1000 m walk"}, r
    r = _tier_count_band(
        [{"name": f"x{i}"} for i in range(2)], th_c,
        rule_label="intl food spots",
        numeric_fmt=lambda n, radius: f"{n} international spots within {radius} m walk",
    )
    assert r["tier"] == "amber" and "2–5 intl food spots within 1km" in r["rule"]
    r = _tier_count_band([], th_c,
        rule_label="intl food spots",
        numeric_fmt=lambda n, radius: f"{n} international spots within {radius} m walk")
    assert r["tier"] == "red" and "<2" in r["rule"]

    # -- Thin wrappers preserve behaviour and produce identical output.
    #    (Exercised in full via scorer.py's regression selfcheck; here just
    #    sanity-check a couple of names route correctly.)
    r_tram = _tier_tram_transit([{"name": "TS", "distance_m": 400}],
                                 {"green_m": 500, "amber_m": 1000})
    assert r_tram["tier"] == "green" and "Tram" in r_tram["numeric"]
    r_bus = _tier_bus_transit([{"name": "BS", "distance_m": 400}],
                               {"green_m": 300, "amber_m": 600})
    assert r_bus["tier"] == "amber" and "Bus" in r_bus["numeric"]
    r_lib = _tier_library([{"name": "L", "distance_m": 999}],
                          {"green_m": 1000, "amber_m": 2500})
    assert r_lib["tier"] == "green" and "library" in r_lib["rule"]
    r_int = _tier_intl_food([{"name": "S"}] * 3,
                             {"radius_m": 1000, "green_count": 6, "amber_count": 2})
    assert r_int["tier"] == "amber" and "international" in r_int["numeric"]
    r_cow = _tier_coworking([],
                             {"radius_m": 1000, "green_count": 3, "amber_count": 1})
    assert r_cow["tier"] == "red" and "remote-work" in r_cow["numeric"]

    # -- Quiet Living tiers -----------------------------------------------

    # Tempo-30 boundaries.
    th_t30 = {"green_kmh": 30, "amber_kmh": 50, "default_kmh": 50}
    r = _tier_tempo30({"speed_kmh": 30, "distance_m": 15,
                       "reason": "verkehrsberuhigt", "time_restriction": None}, th_t30)
    assert r["tier"] == "green" and "30 km/h" in r["numeric"], r
    r = _tier_tempo30({"speed_kmh": 50, "distance_m": 5,
                       "reason": None, "time_restriction": None}, th_t30)
    assert r["tier"] == "amber", r
    r = _tier_tempo30({"speed_kmh": 60, "distance_m": 1,
                       "reason": None, "time_restriction": None}, th_t30)
    assert r["tier"] == "red", r
    # None → default 50 → amber, honest numeric.
    r = _tier_tempo30(None, th_t30)
    assert r["tier"] == "amber" and "assumed 50" in r["numeric"], r
    # Time-restricted Tempo-30 (e.g. school-hour): still counts as green
    # because the exception is present; numeric surfaces the restriction.
    r = _tier_tempo30({"speed_kmh": 30, "distance_m": 20,
                       "reason": None, "time_restriction": "07:00-17:00"},
                      th_t30)
    assert r["tier"] == "green" and "07:00-17:00" in r["numeric"], r

    # Arterial road boundaries.
    th_art = {"green_m": 150, "amber_m": 50}
    r = _tier_arterial_road(None, th_art)
    assert r["tier"] == "green" and "no arterial" in r["numeric"]
    r = _tier_arterial_road({"name": "Torstraße", "class": "II",
                              "distance_m": 200}, th_art)
    assert r["tier"] == "green" and "Torstraße" in r["numeric"]
    r = _tier_arterial_road({"name": "Torstraße", "class": "II",
                              "distance_m": 100}, th_art)
    assert r["tier"] == "amber"
    r = _tier_arterial_road({"name": "Torstraße", "class": "II",
                              "distance_m": 20}, th_art)
    assert r["tier"] == "red"

    # Rail noise boundaries. U-Bahn is always green (underground);
    # S-Bahn scales by distance.
    th_rail = {"green_m": 400, "amber_m": 200}
    assert _tier_rail_noise(None, th_rail)["tier"] == "green"
    assert _tier_rail_noise({"mode": "U-Bahn", "name": "U Turmstr.",
                             "distance_m": 30}, th_rail)["tier"] == "green"
    assert _tier_rail_noise({"mode": "S-Bahn", "name": "S Ostkreuz",
                             "distance_m": 500}, th_rail)["tier"] == "green"
    assert _tier_rail_noise({"mode": "S-Bahn", "name": "S Ostkreuz",
                             "distance_m": 300}, th_rail)["tier"] == "amber"
    assert _tier_rail_noise({"mode": "S-Bahn", "name": "S Ostkreuz",
                             "distance_m": 100}, th_rail)["tier"] == "red"

    # Solo quiet zone (Quiet Living splits from YF's composite refuge).
    th_qz = {"green_m": 400, "amber_m": 1000}
    assert _tier_quiet_zone_solo(None, th_qz)["tier"] == "unknown"
    assert _tier_quiet_zone_solo({"name": "Volkspark", "distance_m": 300}, th_qz)["tier"] == "green"
    assert _tier_quiet_zone_solo({"name": "V", "distance_m": 800}, th_qz)["tier"] == "amber"
    assert _tier_quiet_zone_solo({"name": "V", "distance_m": 2000}, th_qz)["tier"] == "red"

    # Solo street trees.
    th_tr = {"green_pct": 25, "amber_pct": 15}
    assert _tier_street_trees(None, th_tr)["tier"] == "unknown"
    assert _tier_street_trees({"count": 100, "crown_coverage_pct": 30}, th_tr)["tier"] == "green"
    assert _tier_street_trees({"count": 100, "crown_coverage_pct": 20}, th_tr)["tier"] == "amber"
    assert _tier_street_trees({"count": 100, "crown_coverage_pct": 8}, th_tr)["tier"] == "red"

    # Nightlife inverted — for the Quiet Living lens fewer = better.
    th_nl = {"radius_m": 300, "green_max": 3, "amber_max": 8}
    assert _tier_nightlife_inverted([], th_nl)["tier"] == "green"
    assert _tier_nightlife_inverted([{}, {}, {}], th_nl)["tier"] == "green"
    assert _tier_nightlife_inverted([{}] * 4, th_nl)["tier"] == "amber"
    assert _tier_nightlife_inverted([{}] * 8, th_nl)["tier"] == "amber"
    assert _tier_nightlife_inverted([{}] * 9, th_nl)["tier"] == "red"

    print("scoring.tiers selfcheck OK")
