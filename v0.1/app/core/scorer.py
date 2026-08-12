"""Traffic-light noise tier + rule-based stroller score. Verbatim from phase3/server.py.

The JS mirror in web/index.html MUST match stroller_score — the asserts in
__main__ are the reference set. Selfcheck asserts are the exact ones from
phase3/server.py:_selfcheck.
"""

from typing import Optional

from app.core.geo import haversine_m

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


def _walk_minutes(dist_m: float) -> float:
    """Haversine → estimated walking minutes.
    4.8 km/h walking speed × 1.3 route factor ≈ 62 m/min effective.
    Uniform across bureaucracy tiles."""
    return dist_m / 62


# ---------------------------------------------------------------- Spec D
# Feature shape helpers — each _shape_<tile> returns a response-ready
# feature dict, or None if required fields are missing/invalid.

def _prune(d: dict) -> dict:
    """Drop keys whose value is None or empty string. Keeps 0, False, [], {}
    so 'if feature.wheelchair:' still works but 'website: ""' doesn't leak
    an empty link into the response."""
    return {k: v for k, v in d.items() if v not in (None, "")}


def _int_or_none(x):
    """Coerce BOD raw field (str-int like '65' from kita e_platz) to int.
    Returns None on empty/None/unparseable."""
    try:
        return int(x) if x not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _valid_latlon(d: dict) -> bool:
    """Check `lat`/`lon` are finite floats in real-world range. Prevents
    the frontend from trying to pin at (NaN, NaN) or (999, 999)."""
    lat, lon = d.get("lat"), d.get("lon")
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and -90 <= lat <= 90 and -180 <= lon <= 180)


def _shape_kita(o: dict, fm: dict) -> Optional[dict]:
    """Response-shape a kita feature from Index.kitas_near_bod output.
    Required: name, lat, lon, distance_m. All other fields optional and only
    included if the BOD row carries them. Kept in sync with the raw-mode
    kitaDetailHtml popover so Life Mode shows the same rich detail."""
    p = o.get("props") or {}
    street_line = " ".join(x for x in [(p.get("e_strasse") or "").strip(),
                                        (p.get("e_hnr") or "").strip()] if x).strip()
    if p.get("e_zusatz"):
        street_line = (street_line + (p.get("e_zusatz") or "")).strip()
    address = ", ".join(x for x in [street_line, (p.get("e_plz") or "").strip()] if x).strip(", ")
    approaches = " · ".join(x for x in [(p.get("ang_1") or "").strip(),
                                         (p.get("ang_2") or "").strip()] if x)
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "address":       address,
        "phone":        (p.get("e_tel") or "").strip(),
        "website":      (p.get("e_web") or "").strip(),
        "traeger_name": (p.get("t_name") or "").strip(),
        "capacity":       _int_or_none(p.get(fm["capacity"])),
        "operator_type": (p.get(fm["operator_type"]) or "").strip(),
        "approach":      approaches,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_playground(o: dict) -> Optional[dict]:
    """Response-shape a playground feature. BOD side has area (katasterfl
    or nettospfl) + optional renovation year (sanierjahr). OSM side just
    has {name, lat, lon, distance_m}. This shape covers both."""
    p = o.get("props") or {}
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "area_m2":        _int_or_none(p.get("katasterfl") or p.get("nettospfl")),
        "renovated_year": _int_or_none(p.get("sanierjahr")),
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_paediatric_gp(o: dict) -> Optional[dict]:
    """Response-shape a paediatric doctor feature from OSM gps bucket.
    Composes address from OSM addr:* tags. `wheelchair` only surfaced
    when yes (opt-in disclosure of accessibility)."""
    t = o.get("tags") or {}
    street = (t.get("addr:street") or "").strip()
    hnr    = (t.get("addr:housenumber") or "").strip()
    plz    = (t.get("addr:postcode") or "").strip()
    city   = (t.get("addr:city") or "").strip()
    addr_left  = f"{street} {hnr}".strip()
    addr_right = f"{plz} {city}".strip()
    address = ", ".join(p for p in [addr_left, addr_right] if p)

    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "address": address,
        "phone":   (t.get("phone") or "").strip(),
        "website": (t.get("website") or "").strip(),
        "hours":   (t.get("opening_hours") or "").strip(),
        "wheelchair": True if t.get("wheelchair") == "yes" else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_office(o: dict) -> Optional[dict]:
    """Response-shape a bureaucracy office feature. Used for both BOD
    Bürgerämter (which carry address+website already normalized in
    Index.buergeramt_near) and curated federal-directory offices
    (Finanzamt/Standesamt/LEA/Arbeitsagentur — all already
    {name,address,lat,lon,distance_m}).

    walk_min is computed here from distance_m via _walk_minutes and
    rounded to int (matches the tile-face rounding rule from Spec B)."""
    d = o.get("distance_m")
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": d,
        "address": (o.get("address") or "").strip(),
        "website": (o.get("website") or "").strip(),
        "walk_min": round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_transit_stop(o: dict, modality: str) -> Optional[dict]:
    """Shape a transit-stop feature — same field set across S/U/Tram/Bus so the
    YF Transit tile can render a uniform list. `modality` is one of
    'S-Bahn' / 'U-Bahn' / 'Tram' / 'Bus'. Required: name, lat, lon, distance_m."""
    if not o:
        return None
    d = o.get("distance_m")
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": d,
        "modality":   modality,
        "walk_min":   round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_supermarket(o: dict) -> Optional[dict]:
    """Shape a supermarket feature. Data comes from OSM (Berlin has no BOD
    supermarket layer). Required: name, lat, lon, distance_m."""
    if not o:
        return None
    d = o.get("distance_m")
    t = o.get("tags") or {}
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": d,
        "walk_min":   round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
        "brand":         (t.get("brand") or "").strip(),
        "opening_hours": (t.get("opening_hours") or "").strip(),
        "wheelchair":    True if t.get("wheelchair") == "yes" else None,
        "organic":       True if t.get("organic") == "yes" else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


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
    g is the dict returned by Index.gesix_at, or None.
    Mapping — top two quintiles green, middle quintile amber, bottom two red.
    Explicit unknown when the address sits outside any polygon (rare)."""
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


def _shape_refuge_quiet(q: dict, amber_quiet_m: int) -> list:
    """Return [feature] iff the quiet zone is within amber radius; else [].
    Refuge is composite (quiet zone OR tree crown) — a tile that went
    amber via TREES alone should NOT surface a distant quiet zone as a
    feature because the map pin would be misleading."""
    if not q or q.get("distance_m") is None:
        return []
    if q["distance_m"] > amber_quiet_m:
        return []
    r = _prune({
        "name": (q.get("name") or "").strip() or "Quiet zone",
        "lat":  q.get("lat"), "lon": q.get("lon"),
        "distance_m": q.get("distance_m"),
        "size_ha": q.get("size_ha"),
        "kind":    q.get("kind"),
    })
    if not _valid_latlon(r):
        return []
    return [r]


def _shape_refuge_trees(t: dict) -> dict:
    """Return trees summary for refuge tile's metadata. Passes through
    Index.trees_bbox keys, pruned. Returns {} if trees fetch failed
    (frontend hides the trees block when empty)."""
    if not t or t.get("error"):
        return {}
    top = t.get("top_species") or []
    return _prune({
        "count":               t.get("count"),
        "avg_age_yr":          t.get("avg_age_yr"),
        "tallest_m":           t.get("tallest_m"),
        "crown_coverage_pct":  t.get("crown_coverage_pct"),
        "top_species": [{"name": s.get("name"), "n": s.get("n")}
                        for s in top[:5] if s.get("name")],
    })


def _tier_buergeramt(offices: list, t: dict) -> dict:
    """Bürgeramt — nearest of many (Berlin is free choice)."""
    if not offices:
        return {"tier": TIER_UNKNOWN,
                "rule": "Bürgeramt data unavailable",
                "numeric": "no Bürgeramt loaded"}
    nearest = offices[0]
    m = _walk_minutes(nearest["distance_m"])
    within_green = sum(1 for o in offices
                       if _walk_minutes(o["distance_m"]) <= t["green_min"])
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"≥1 Bürgeramt within {t['green_min']} min walk",
                "numeric": (f"{within_green} within {t['green_min']} min · "
                            f"nearest {round(m)} min ({nearest['name']})")}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Bürgeramt {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"nearest {round(m)} min ({nearest['name']})"}
    return {"tier": TIER_RED,
            "rule": f"no Bürgeramt within {t['amber_min']} min walk",
            "numeric": f"nearest {round(m)} min ({nearest['name']})"}


def _tier_finanzamt(office: dict, t: dict) -> dict:
    """Finanzamt — nearest single office. `office` is the pre-selected
    nearest from Index.finanzamt_nearest()."""
    if not office:
        return {"tier": TIER_UNKNOWN,
                "rule": "Finanzamt data unavailable",
                "numeric": "no Finanzamt loaded"}
    m = _walk_minutes(office["distance_m"])
    label = office["name"]
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"Finanzamt within {t['green_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Finanzamt {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    return {"tier": TIER_RED,
            "rule": f"Finanzamt > {t['amber_min']} min walk",
            "numeric": f"{round(m)} min ({label})"}


def _tier_standesamt(office: dict, t: dict) -> dict:
    """Standesamt — the pre-assigned office for the address's Bezirk.
    `office` is None only if bezirk_for() returned None (address outside
    Berlin's Bezirksgrenzen)."""
    if not office:
        return {"tier": TIER_UNKNOWN,
                "rule": "Standesamt not determined",
                "numeric": "Address is outside Berlin's Bezirksgrenzen"}
    m = _walk_minutes(office["distance_m"])
    label = office["name"]
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"assigned Standesamt within {t['green_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Standesamt {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    return {"tier": TIER_RED,
            "rule": f"assigned Standesamt > {t['amber_min']} min walk",
            "numeric": f"{round(m)} min ({label})"}


def _tier_lea(office: dict, t: dict) -> dict:
    """LEA — single central office. `office` includes `distance_m`
    (added by the composer from cfg.lea_office)."""
    if not office or "distance_m" not in office:
        return {"tier": TIER_UNKNOWN,
                "rule": "LEA data unavailable",
                "numeric": "cfg.lea_office malformed"}
    m = _walk_minutes(office["distance_m"])
    label = office["name"]
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"LEA within {t['green_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"LEA {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    return {"tier": TIER_RED,
            "rule": f"LEA > {t['amber_min']} min walk",
            "numeric": f"{round(m)} min ({label})"}


def _tier_arbeitsagentur(offices: list, t: dict) -> dict:
    """Arbeitsagentur — nearest of many (free choice)."""
    if not offices:
        return {"tier": TIER_UNKNOWN,
                "rule": "Arbeitsagentur data unavailable",
                "numeric": "no Arbeitsagentur loaded"}
    nearest = offices[0]
    m = _walk_minutes(nearest["distance_m"])
    within_green = sum(1 for o in offices
                       if _walk_minutes(o["distance_m"]) <= t["green_min"])
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"≥1 Arbeitsagentur within {t['green_min']} min walk",
                "numeric": (f"{within_green} within {t['green_min']} min · "
                            f"nearest {round(m)} min ({nearest['name']})")}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Arbeitsagentur {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"nearest {round(m)} min ({nearest['name']})"}
    return {"tier": TIER_RED,
            "rule": f"no Arbeitsagentur within {t['amber_min']} min walk",
            "numeric": f"nearest {round(m)} min ({nearest['name']})"}


def bureaucracy_lens(cfg, index, lon: float, lat: float) -> dict:
    """Assemble 5 tile results for one address. Pure — no I/O on the hot path.

    Reads preloaded data from Index (Bezirksgrenzen, Bürgerämter) and
    curated data from CityConfig (Finanzamt / Standesamt / Arbeitsagentur
    / LEA directories). No external fetches — bureaucracy is deterministic
    (same inputs → byte-for-byte identical output).
    """
    lens = cfg.bureaucracy_lens
    thresholds = {t.key: t.thresholds for t in lens.tiles}
    tile_meta  = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    buergeramts    = index.buergeramt_near(lon, lat)
    finanzamt      = index.finanzamt_nearest(lon, lat)
    standesamt     = index.standesamt_for(lon, lat)             # None if outside Berlin
    lea            = _with_distance(cfg.lea_office, lon, lat)   # LEA is a single point
    arbeitsagentur = index.arbeitsagentur_near(lon, lat)

    results = [
        ("buergeramt",     _tier_buergeramt(buergeramts, thresholds["buergeramt"])),
        ("finanzamt",      _tier_finanzamt(finanzamt, thresholds["finanzamt"])),
        ("standesamt",     _tier_standesamt(standesamt, thresholds["standesamt"])),
        ("lea",            _tier_lea(lea, thresholds["lea"])),
        ("arbeitsagentur", _tier_arbeitsagentur(arbeitsagentur, thresholds["arbeitsagentur"])),
    ]

    tiles = []
    for key, res in results:
        label, icon, caveat = tile_meta[key]
        tile = {
            "key":     key,
            "label":   label,
            "icon":    icon,
            "tier":    res["tier"],
            "rule":    res["rule"],
            "numeric": res["numeric"],
            "caveat":  caveat,
            "sources": _sources_for(cfg, key, res["tier"]),
        }
        # -- Spec D: features per bureaucracy tile ---------------------------
        if key == "buergeramt":
            tile["features"] = [f for f in
                (_shape_office(o) for o in buergeramts) if f]
        elif key == "arbeitsagentur":
            tile["features"] = [f for f in
                (_shape_office(o) for o in arbeitsagentur) if f]
        elif key == "finanzamt":
            single = _shape_office(finanzamt) if finanzamt else None
            tile["features"] = [single] if single else []
        elif key == "standesamt":
            single = _shape_office(standesamt) if standesamt else None
            tile["features"] = [single] if single else []
        elif key == "lea":
            single = _shape_office(lea) if lea else None
            tile["features"] = [single] if single else []
        else:
            tile["features"] = []
        tiles.append(tile)

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }


def _with_distance(office: dict, lon: float, lat: float) -> dict:
    """Return office dict with `distance_m` added. Used for the single-point
    LEA (cfg.lea_office doesn't come pre-decorated with distance)."""
    if not office or "lon" not in office or "lat" not in office:
        return None
    d = haversine_m(lon, lat, office["lon"], office["lat"])
    return {**office, "distance_m": round(d)}


def _lens_provenance(cfg, tiles: list) -> str:
    """Union of `sources` from tiles that contributed a real tier — de-duped,
    insertion-order preserved (Python 3.7+ dict semantics). Unknown tiles
    contribute [], so they're skipped naturally. Empty string if nothing to
    cite; frontend hides the provenance footer in that case (§14.5)."""
    seen, out = set(), []
    for tile in tiles:
        for s in (tile.get("sources") or []):
            if s and s not in seen:
                seen.add(s); out.append(s)
    return " · ".join(out)


def _sources_for(cfg, key: str, tier: str) -> list:
    """Return the `sources` array for one tile. Unknown tiles get []. Every
    string is looked up in cfg.attribution — never invent a provenance line.
    Empty strings dropped so a missing attribution key doesn't leak an empty
    citation."""
    if tier == TIER_UNKNOWN:
        return []
    attr = cfg.attribution
    mapping = {
        "kita":         [attr.get("kitas")],
        "playground":   [attr.get("playgrounds"),
                         attr.get("parks"),
                         "© OpenStreetMap contributors (ODbL)"],
        "pediatrician": ["© OpenStreetMap contributors (ODbL)"],
        "noise":        [attr.get("noise")],
        "heat":         [attr.get("heat")],
        "air":          [attr.get("air")],
        "refuge":       [attr.get("quiet_zone"), attr.get("trees")],
        "transit":      [attr.get("sbahn"), attr.get("ubahn"), attr.get("tram"),
                         "© OpenStreetMap contributors (ODbL) — bus stops"],
        "supermarket":  ["© OpenStreetMap contributors (ODbL)"],
        "gesix":        [attr.get("gesix")],
        # Spec B — Bureaucracy lens
        "buergeramt":     [attr.get("buergeramt")],
        "finanzamt":      [attr.get("finanzamt")],
        "standesamt":     [attr.get("standesamt"), attr.get("bezirksgrenzen")],
        "lea":            [attr.get("lea")],
        "arbeitsagentur": [attr.get("arbeitsagentur")],
    }
    return [s for s in (mapping.get(key) or []) if s]


def young_family_lens(cfg, index, lon: float, lat: float, *,
                      air: dict, heat: dict, noise: dict,
                      amenities: dict, trees: dict, quiet_zone: dict) -> dict:
    """Assemble 7 tile results for one address. Pure — no I/O.

    All inputs are values already computed elsewhere in /api/lookup;
    the lens is a view over data the address already carries. Never call
    WFS from here — that keeps the lens from ever disagreeing with the
    raw data in the same response.
    """
    from app.core.amenities import is_paediatric

    lens = cfg.young_family_lens
    thresholds  = {t.key: t.thresholds       for t in lens.tiles}
    tile_meta   = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    kitas = index.kitas_near_bod(lon, lat, 800)

    pg_block  = (amenities or {}).get("playgrounds") or {}
    pg_items  = pg_block.get("items") or []
    pg_error  = bool(pg_block.get("error") or pg_block.get("_error"))

    gps_block = (amenities or {}).get("gps") or {}
    gps_items = gps_block.get("items") or []
    gps_error = bool(gps_block.get("error") or gps_block.get("_error"))
    paediatric = [g for g in gps_items if is_paediatric(g.get("tags"))]
    paediatric.sort(key=lambda x: x.get("distance_m", 10**9))

    # Transit — nearest of each modality (S/U/Tram from Index BOD/VBB, Bus from
    # OSM Overpass via amenities transit bucket). Consolidated into a single
    # feature list; tier reads off the minimum walk_min across all modes.
    _transit_feats = []
    for modality, points in (("S-Bahn", index.sbahn),
                              ("U-Bahn", index.ubahn),
                              ("Tram",   index.tram)):
        nearest = index.nearest_station(points, lon, lat)
        f = _shape_transit_stop(nearest, modality) if nearest else None
        if f:
            _transit_feats.append(f)
    # Bus stops via OSM (Overpass) — nearest bus-tagged transit item.
    _tr_block = (amenities or {}).get("transit") or {}
    _tr_items = _tr_block.get("items") or []
    _bus_items = [it for it in _tr_items if (it.get("tags") or {}).get("bus") == "yes"
                                          or (it.get("tags") or {}).get("highway") == "bus_stop"]
    if _bus_items:
        _bus_items.sort(key=lambda x: x.get("distance_m", 10**9))
        f_bus = _shape_transit_stop(_bus_items[0], "Bus")
        if f_bus:
            _transit_feats.append(f_bus)
    _transit_feats.sort(key=lambda x: x.get("walk_min", 10**9))

    # Supermarkets — OSM-only; take nearest first from amenities bucket.
    _sm_block = (amenities or {}).get("supermarkets") or {}
    _sm_items = _sm_block.get("items") or []
    _sm_error = bool(_sm_block.get("error") or _sm_block.get("_error"))
    _sm_feats = [f for f in (_shape_supermarket(o) for o in _sm_items) if f]
    _sm_feats.sort(key=lambda x: x.get("walk_min", 10**9))

    # GESIx (Berlin Senate 2022 health & social composite per Planungsraum).
    # Index.gesix_at returns None outside covered polygons — _tier_gesix
    # handles that with tier=unknown.
    _gesix = index.gesix_at(lon, lat) if hasattr(index, "gesix_at") else None

    results = [
        ("kita",         _tier_kita(kitas, thresholds["kita"])),
        ("playground",   _tier_playground(pg_items, pg_error, thresholds["playground"])),
        ("pediatrician", _tier_pediatrician(paediatric, gps_error, thresholds["pediatrician"])),
        ("transit",      _tier_transit(_transit_feats, thresholds["transit"])),
        ("supermarket",  (_tier_supermarket(_sm_feats, thresholds["supermarket"])
                           if not _sm_error
                           else {"tier": TIER_UNKNOWN,
                                 "rule": "Supermarket data unavailable",
                                 "numeric": "OSM Overpass unavailable"})),
        ("gesix",        _tier_gesix(_gesix)),
        ("noise",        _tier_noise(noise, thresholds["noise"])),
        ("heat",         _tier_heat(heat, thresholds["heat"])),
        ("air",          _tier_air(air, thresholds["air"])),
        ("refuge",       _tier_refuge(quiet_zone, trees, thresholds["refuge"])),
    ]

    tiles = []
    for key, res in results:
        label, icon, caveat = tile_meta[key]
        tile = {
            "key":     key,
            "label":   label,
            "icon":    icon,
            "tier":    res["tier"],
            "rule":    res["rule"],
            "numeric": res["numeric"],
            "caveat":  caveat,
            "sources": _sources_for(cfg, key, res["tier"]),
        }
        # -- Spec D: features per tile ---------------------------------------
        if key == "kita":
            tile["features"] = [f for f in
                (_shape_kita(o, cfg.kita_field_map) for o in kitas) if f]
        elif key == "playground":
            tile["features"] = [f for f in
                (_shape_playground(o) for o in pg_items) if f]
        elif key == "pediatrician":
            tile["features"] = [f for f in
                (_shape_paediatric_gp(o) for o in paediatric) if f]
        elif key == "refuge":
            tile["features"] = _shape_refuge_quiet(
                quiet_zone, thresholds["refuge"]["amber_quiet_m"])
            tile["metadata"] = {"trees": _shape_refuge_trees(trees)}
        elif key == "transit":
            tile["features"] = _transit_feats
        elif key == "supermarket":
            tile["features"] = _sm_feats[:10]      # top 10 nearest for the modal
        elif key == "gesix":
            # Aggregate index — no features. Payload for the frontend chart +
            # AI-insight modal goes on metadata so it doesn't accidentally
            # get plotted as a map pin.
            tile["features"] = []
            tile["metadata"] = {"gesix": _gesix} if _gesix else {}
        else:
            # noise, heat, air — aggregate readings, no per-feature list
            tile["features"] = []
        tiles.append(tile)

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }


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

    # -- Sources composition + de-dup order --------------------------------
    _fake_tiles = [
        {"sources": ["A", "B"]},
        {"sources": []},                    # unknown-shaped, contributes nothing
        {"sources": ["B", "C", "A"]},       # duplicates suppressed, order kept
        {"sources": None},                  # tolerated
    ]
    assert _lens_provenance(_CFG_YF, _fake_tiles) == "A · B · C"
    assert _lens_provenance(_CFG_YF, [{"sources": []}, {"sources": None}]) == ""

    # -- Caveat pass-through -----------------------------------------------
    _caveats = {t.key: t.caveat for t in _CFG_YF.young_family_lens.tiles}
    assert _caveats["pediatrician"], "pediatrician tile must carry a caveat"
    assert _caveats["kita"] == "" and _caveats["noise"] == ""

    # -- Empty-but-available inputs → red (kita has 0 nearby, noise=100 dB, etc.)
    #    Uses a stub for the only Index method the composer calls.
    class _StubIndex:
        sbahn = ubahn = tram = []
        def kitas_near_bod(self, lon, lat, r): return []
        def nearest_station(self, points, lon, lat): return None
        def gesix_at(self, lon, lat): return None
    _empty_result = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 60}, heat={"day_class": "extreme Belastung"},
        noise={"l_den": {"total": 70}},
        amenities={"playgrounds": {"items": []}, "gps": {"items": []}},
        trees={"crown_coverage_pct": 5},
        quiet_zone={"distance_m": 5000},
    )
    _tiers = {t["key"]: t["tier"] for t in _empty_result["tiles"]}
    # Transit tile is 'unknown' when no station data reaches the composer (stub
    # returns None for every modality); everything else is 'red' with the
    # bad-signal inputs above.
    # Transit + gesix are 'unknown' when their inputs are absent from the
    # stub Index; everything else is 'red' with the bad-signal inputs above.
    assert _tiers.pop("transit") == TIER_UNKNOWN, _tiers
    assert _tiers.pop("gesix")   == TIER_UNKNOWN, _tiers
    assert all(v == TIER_RED for v in _tiers.values()), _tiers

    # -- Unavailable inputs → unknown where possible, red where not ---------
    _unavail_result = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"unavailable": True}, heat={"unavailable": True},
        noise={"unavailable": True},
        amenities={"playgrounds": {"items": [], "error": "overpass timeout"},
                   "gps":         {"items": [], "error": "overpass timeout"}},
        trees=None, quiet_zone=None,
    )
    _u = {t["key"]: t["tier"] for t in _unavail_result["tiles"]}
    assert _u["noise"]        == TIER_UNKNOWN
    assert _u["heat"]         == TIER_UNKNOWN
    assert _u["air"]          == TIER_UNKNOWN
    assert _u["playground"]   == TIER_UNKNOWN
    assert _u["pediatrician"] == TIER_UNKNOWN
    assert _u["refuge"]       == TIER_UNKNOWN
    assert _u["kita"]         == TIER_RED   # preloaded — unknown unreachable

    # Response shape stability (every tile has features; refuge also has metadata).
    _base_keys = {"key","label","icon","tier","rule","numeric","caveat","sources","features"}
    for t in _unavail_result["tiles"]:
        assert _base_keys <= set(t.keys()), t
    _refuge_u = next(t for t in _unavail_result["tiles"] if t["key"] == "refuge")
    assert "metadata" in _refuge_u and "trees" in _refuge_u["metadata"]
    assert _unavail_result["slug"]     == "young_family"
    assert _unavail_result["label"]    == "Young Family (0–6)"
    assert _unavail_result["audience"] == "For a family with kids under 6"
    # kita is red (not unknown) → DOES cite its attribution source.
    assert "Kindertagesstätten" in _unavail_result["provenance"], _unavail_result["provenance"]

    # -- Spec D: features on young_family output ----------------------------
    _r_full = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 15}, heat={"day_class": "geringe Belastung"},
        noise={"l_den": {"total": 50}},
        amenities={"playgrounds": {"items": [
            {"name": "P1", "lat": 52.5, "lon": 13.4, "distance_m": 350,
             "props": {"katasterfl": 500}}]},
                   "gps": {"items": []}},
        trees={"count": 40, "crown_coverage_pct": 30,
               "top_species": [{"name":"Silberlinde","n":10}]},
        quiet_zone={"name": "Q", "lat": 52.5, "lon": 13.4, "distance_m": 380},
    )
    _by = {t["key"]: t for t in _r_full["tiles"]}
    # Every tile has `features` key
    for k in ["kita","playground","pediatrician","noise","heat","air","refuge"]:
        assert "features" in _by[k], f"{k} missing features"
    # Aggregate tiles → []
    assert _by["noise"]["features"] == []
    assert _by["heat"]["features"]  == []
    assert _by["air"]["features"]   == []
    # Refuge always carries metadata.trees (populated or empty dict)
    assert "metadata" in _by["refuge"]
    assert "trees" in _by["refuge"]["metadata"]
    # Playground feature shaped correctly
    assert _by["playground"]["features"] == [
        {"name":"P1","lat":52.5,"lon":13.4,"distance_m":350,"area_m2":500}]
    # Refuge quiet zone becomes 1 feature (within 400m green threshold)
    assert len(_by["refuge"]["features"]) == 1
    assert _by["refuge"]["features"][0]["name"] == "Q"

    # Refuge with quiet zone BEYOND amber: features drops to []
    _r_no_quiet = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 15}, heat={"day_class": "geringe Belastung"},
        noise={"l_den": {"total": 50}},
        amenities={"playgrounds": {"items": []}, "gps": {"items": []}},
        trees={"count": 40, "crown_coverage_pct": 30},
        quiet_zone={"name":"Far","lat":52.6,"lon":13.5,"distance_m":5000},
    )
    _rf = next(t for t in _r_no_quiet["tiles"] if t["key"] == "refuge")
    assert _rf["features"] == []
    assert _rf["metadata"]["trees"]["crown_coverage_pct"] == 30

    print("scorer.py: young_family composer + provenance OK")

    # -- Bureaucracy lens: boundary sweeps (Spec B pure selfcheck) ----------
    from app.cities.berlin import BERLIN as _CFG_BUR
    _TB = {t.key: t.thresholds for t in _CFG_BUR.bureaucracy_lens.tiles}

    # _walk_minutes sanity
    assert _walk_minutes(0)   == 0.0
    assert _walk_minutes(62)  == 1.0
    assert abs(_walk_minutes(930) - 15.0) < 1e-9

    # _tier_buergeramt — nearest of many
    _B930 = [{"name":"BA-A","distance_m":930}]
    _B931 = [{"name":"BA-B","distance_m":931}]
    assert _tier_buergeramt(_B930, _TB["buergeramt"])["tier"] == TIER_GREEN
    assert _tier_buergeramt(_B931, _TB["buergeramt"])["tier"] == TIER_AMBER
    assert _tier_buergeramt([{"name":"X","distance_m":1860}], _TB["buergeramt"])["tier"] == TIER_AMBER
    assert _tier_buergeramt([{"name":"X","distance_m":1861}], _TB["buergeramt"])["tier"] == TIER_RED
    assert _tier_buergeramt([], _TB["buergeramt"])["tier"] == TIER_UNKNOWN

    # _tier_finanzamt — nearest single office (dict, not list)
    assert _tier_finanzamt({"name":"FA","distance_m":930}, _TB["finanzamt"])["tier"] == TIER_GREEN
    assert _tier_finanzamt({"name":"FA","distance_m":931}, _TB["finanzamt"])["tier"] == TIER_AMBER
    assert _tier_finanzamt({"name":"FA","distance_m":1860}, _TB["finanzamt"])["tier"] == TIER_AMBER
    assert _tier_finanzamt({"name":"FA","distance_m":1861}, _TB["finanzamt"])["tier"] == TIER_RED
    assert _tier_finanzamt(None, _TB["finanzamt"])["tier"] == TIER_UNKNOWN

    # _tier_standesamt — pre-assigned dict
    assert _tier_standesamt({"name":"SA","distance_m":930}, _TB["standesamt"])["tier"] == TIER_GREEN
    assert _tier_standesamt({"name":"SA","distance_m":931}, _TB["standesamt"])["tier"] == TIER_AMBER
    assert _tier_standesamt({"name":"SA","distance_m":1860}, _TB["standesamt"])["tier"] == TIER_AMBER
    assert _tier_standesamt({"name":"SA","distance_m":1861}, _TB["standesamt"])["tier"] == TIER_RED
    assert _tier_standesamt(None, _TB["standesamt"])["tier"] == TIER_UNKNOWN

    # _tier_lea — single dict with distance_m
    assert _tier_lea({"name":"LEA","distance_m":930}, _TB["lea"])["tier"] == TIER_GREEN
    assert _tier_lea({"name":"LEA","distance_m":931}, _TB["lea"])["tier"] == TIER_AMBER
    assert _tier_lea({"name":"LEA","distance_m":1860}, _TB["lea"])["tier"] == TIER_AMBER
    assert _tier_lea({"name":"LEA","distance_m":1861}, _TB["lea"])["tier"] == TIER_RED
    assert _tier_lea(None, _TB["lea"])["tier"] == TIER_UNKNOWN
    assert _tier_lea({"name":"LEA"}, _TB["lea"])["tier"] == TIER_UNKNOWN  # missing distance_m

    # _tier_arbeitsagentur — same shape as buergeramt
    _A930 = [{"name":"AA-A","distance_m":930}]
    _A931 = [{"name":"AA-B","distance_m":931}]
    assert _tier_arbeitsagentur(_A930, _TB["arbeitsagentur"])["tier"] == TIER_GREEN
    assert _tier_arbeitsagentur(_A931, _TB["arbeitsagentur"])["tier"] == TIER_AMBER
    assert _tier_arbeitsagentur([{"name":"X","distance_m":1861}], _TB["arbeitsagentur"])["tier"] == TIER_RED
    assert _tier_arbeitsagentur([], _TB["arbeitsagentur"])["tier"] == TIER_UNKNOWN

    print("scorer.py: bureaucracy tier boundary sweeps OK")

    # -- Bureaucracy composer — determinism, outside-Berlin, all-empty ------
    class _StubIndex:
        def __init__(self, bezirk="Pankow"):
            self._bezirk = bezirk
        def bezirk_for(self, lon, lat): return self._bezirk
        def buergeramt_near(self, lon, lat, radius_m=3000):
            return [{"name":"BA-Test","lat":52.5,"lon":13.4,"distance_m":500}]
        def arbeitsagentur_near(self, lon, lat, radius_m=5000):
            return [{"name":"AA-Test","lat":52.5,"lon":13.4,"distance_m":800}]
        def finanzamt_nearest(self, lon, lat):
            return {"name":"FA-Test","lat":52.5,"lon":13.4,"distance_m":600}
        def standesamt_for(self, lon, lat):
            if not self._bezirk: return None
            return {"name": f"Standesamt {self._bezirk}","lat":52.5,"lon":13.4,"distance_m":700}

    # Determinism — two identical calls must produce byte-equal dicts.
    r_a = bureaucracy_lens(_CFG_BUR, _StubIndex(), 13.4, 52.5)
    r_b = bureaucracy_lens(_CFG_BUR, _StubIndex(), 13.4, 52.5)
    assert r_a == r_b, "bureaucracy_lens must be deterministic"

    # All 5 tiles present, keys in expected order.
    _keys = [t["key"] for t in r_a["tiles"]]
    assert _keys == ["buergeramt","finanzamt","standesamt","lea","arbeitsagentur"], _keys

    # Response shape stability (every tile has all 9 keys).
    for t in r_a["tiles"]:
        assert set(t.keys()) == {"key","label","icon","tier","rule","numeric","caveat","sources","features"}, t
    assert r_a["slug"] == "bureaucracy"
    assert r_a["label"] == "Bureaucracy"

    # Caveat pass-through
    _caveats = {t.key: t.caveat for t in _CFG_BUR.bureaucracy_lens.tiles}
    assert _caveats["buergeramt"], "Bürgeramt tile must carry a caveat"
    assert "Steuernummer" in _caveats["finanzamt"]
    assert "Specialty branches" in _caveats["lea"]
    assert _caveats["standesamt"] == "" and _caveats["arbeitsagentur"] == ""

    # Outside-Berlin — bezirk_for returns None → Standesamt goes unknown
    r_out = bureaucracy_lens(_CFG_BUR, _StubIndex(bezirk=None), 13.4, 52.5)
    _by_out = {t["key"]: t["tier"] for t in r_out["tiles"]}
    assert _by_out["standesamt"] == "unknown", _by_out

    # Empty inputs → red, not unknown (for the "list of many" tiles)
    class _StubEmpty(_StubIndex):
        def buergeramt_near(self, lon, lat, radius_m=3000): return []
        def arbeitsagentur_near(self, lon, lat, radius_m=5000): return []
    r_empty = bureaucracy_lens(_CFG_BUR, _StubEmpty(), 13.4, 52.5)
    _by_empty = {t["key"]: t["tier"] for t in r_empty["tiles"]}
    # Empty preloaded list → UNKNOWN (list "unavailable" from preload failure)
    # For "list of many" tiles, empty-list is genuinely ambiguous — the tier
    # function goes unknown when it can't find any office. This matches Spec A
    # semantics for playground-when-both-sources-fail.
    assert _by_empty["buergeramt"] == "unknown"
    assert _by_empty["arbeitsagentur"] == "unknown"

    # Provenance: for the determinism case (all non-unknown), provenance must
    # cite the sources of all 5 tiles' contributed attribution keys.
    assert "Bürgerämter" in r_a["provenance"], r_a["provenance"]
    assert "Finanzamt" in r_a["provenance"] or "Finanzämter" in r_a["provenance"]

    # -- Spec D: features on bureaucracy output ----------------------------
    _r_bur_full = bureaucracy_lens(_CFG_BUR, _StubIndex(), 13.4, 52.5)
    _by_bur = {t["key"]: t for t in _r_bur_full["tiles"]}
    # Every bureaucracy tile has features
    for k in ["buergeramt","finanzamt","standesamt","lea","arbeitsagentur"]:
        assert "features" in _by_bur[k], f"{k} missing features"
    # Nearest-single tiles have exactly 1 feature (when stub returns them)
    assert len(_by_bur["finanzamt"]["features"])  == 1
    assert len(_by_bur["standesamt"]["features"]) == 1
    assert len(_by_bur["lea"]["features"])        == 1
    # Every feature has walk_min (int, from _shape_office)
    for k in ["buergeramt","finanzamt","standesamt","lea","arbeitsagentur"]:
        for f in _by_bur[k]["features"]:
            assert isinstance(f.get("walk_min"), int), f
    # Malformed input → filtered out
    class _StubEmpty(_StubIndex):
        def buergeramt_near(self, lon, lat, r=3000): return []
        def arbeitsagentur_near(self, lon, lat, r=5000): return []
        def finanzamt_nearest(self, lon, lat): return None
        def standesamt_for(self, lon, lat): return None
    # LEA feature will still be present (comes from cfg.lea_office, not the index)
    _r_empty = bureaucracy_lens(_CFG_BUR, _StubEmpty(), 13.4, 52.5)
    _bym = {t["key"]: t for t in _r_empty["tiles"]}
    assert _bym["buergeramt"]["features"]     == []
    assert _bym["arbeitsagentur"]["features"] == []
    assert _bym["finanzamt"]["features"]      == []
    assert _bym["standesamt"]["features"]     == []

    print("scorer.py: bureaucracy composer OK")

    # -- Spec D shape helpers -----------------------------------------------
    # _prune drops None + "" but keeps 0, False, [], {}
    assert _prune({"a":"x","b":None,"c":"","d":0,"e":False,"f":[],"g":{}}) \
        == {"a":"x","d":0,"e":False,"f":[],"g":{}}

    # _int_or_none
    assert _int_or_none("65") == 65
    assert _int_or_none(65)   == 65
    assert _int_or_none(None) is None
    assert _int_or_none("")   is None
    assert _int_or_none("abc") is None

    # _valid_latlon
    assert _valid_latlon({"lat": 52.5, "lon": 13.4}) is True
    assert _valid_latlon({"lat": 100.0, "lon": 13.4}) is False
    assert _valid_latlon({"lat": None, "lon": 13.4})  is False
    assert _valid_latlon({"lat": 52.5})                is False

    # _shape_kita — realistic BOD input
    _fm_k = _CFG_YF.kita_field_map
    _raw = {"name": "Kita Sonnenschein",
            "lat": 52.5388, "lon": 13.3948, "distance_m": 180,
            "props": {_fm_k["capacity"]: "65",
                      _fm_k["operator_type"]: "freie Träger",
                      _fm_k["approach"]: "Situationsansatz"}}
    assert _shape_kita(_raw, _fm_k) == {
        "name": "Kita Sonnenschein",
        "lat": 52.5388, "lon": 13.3948, "distance_m": 180,
        "capacity": 65, "operator_type": "freie Träger",
        "approach": "Situationsansatz"}
    # Drops when required fields missing
    assert _shape_kita({"name": "", "lat": 52.5, "lon": 13.4,
                        "distance_m": 100, "props": {}}, _fm_k) is None
    assert _shape_kita({"name": "X", "distance_m": 100, "props": {}}, _fm_k) is None

    # _shape_playground
    _pg = {"name": "Marheinekeplatz, Spiel", "lat": 52.489, "lon": 13.396,
           "distance_m": 75, "props": {"katasterfl": 446, "sanierjahr": "2018"}}
    assert _shape_playground(_pg) == {
        "name": "Marheinekeplatz, Spiel",
        "lat": 52.489, "lon": 13.396, "distance_m": 75,
        "area_m2": 446, "renovated_year": 2018}
    _pg_bare = {"name": "P2", "lat": 52.5, "lon": 13.4, "distance_m": 200,
                "props": {}}
    assert _shape_playground(_pg_bare) == {
        "name": "P2", "lat": 52.5, "lon": 13.4, "distance_m": 200}

    # _shape_paediatric_gp — realistic OSM tags
    _gp = {"name": "Praxis für Kinderheilkunde Dr. Berns",
           "lat": 52.4893, "lon": 13.3889, "distance_m": 430,
           "tags": {"addr:street": "Bergmannstraße", "addr:housenumber": "5",
                    "addr:postcode": "10961", "addr:city": "Berlin",
                    "phone": "+49 30 693 80 05",
                    "website": "https://kinderarztpraxis-berns.de",
                    "opening_hours": "Mo-Fr 09:00-12:00; Mo,Tu,Th 15:00-18:00",
                    "wheelchair": "yes"}}
    _rgp = _shape_paediatric_gp(_gp)
    assert _rgp["address"] == "Bergmannstraße 5, 10961 Berlin"
    assert _rgp["phone"]   == "+49 30 693 80 05"
    assert _rgp["website"] == "https://kinderarztpraxis-berns.de"
    assert _rgp["hours"].startswith("Mo-Fr")
    assert _rgp["wheelchair"] is True
    # wheelchair only surfaces on "yes" (not "limited" / "no" / missing)
    _gp2 = {**_gp, "tags": {**_gp["tags"], "wheelchair": "limited"}}
    assert "wheelchair" not in _shape_paediatric_gp(_gp2)

    # _shape_office — walk_min computed via _walk_minutes and rounded
    _off = {"name": "Bürgeramt X",
            "address": "Y-Str. 1, 10000 Berlin",
            "lat": 52.5, "lon": 13.4, "distance_m": 620,
            "website": "https://x.example/"}
    _roff = _shape_office(_off)
    assert _roff["walk_min"] == 10        # 620 / 62 = 10.0
    assert _roff["website"]  == "https://x.example/"

    # _shape_refuge_quiet — within amber returns [feature]; beyond returns []
    _q_within = {"name": "Volkspark", "lat": 52.53, "lon": 13.42,
                 "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet"}
    assert _shape_refuge_quiet(_q_within, 1000) == [{
        "name": "Volkspark", "lat": 52.53, "lon": 13.42,
        "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet"}]
    assert _shape_refuge_quiet({"name": "Far", "lat": 52.6, "lon": 13.5,
                                "distance_m": 5000}, 1000) == []
    assert _shape_refuge_quiet(None, 1000) == []

    # _shape_refuge_trees — pass through, drop empties, cap top_species
    _tr = {"count": 42, "avg_age_yr": 35, "tallest_m": 22,
           "crown_coverage_pct": 27,
           "top_species": [{"name":"Silberlinde","n":12},
                           {"name":"Winterlinde","n":8},
                           {"name":"","n":0}]}
    _rtr = _shape_refuge_trees(_tr)
    assert _rtr["count"] == 42
    assert _rtr["top_species"] == [{"name":"Silberlinde","n":12},
                                    {"name":"Winterlinde","n":8}]
    assert _shape_refuge_trees({"error": "trees down"}) == {}
    assert _shape_refuge_trees(None) == {}

    print("scorer.py: Spec D shape helpers OK")
