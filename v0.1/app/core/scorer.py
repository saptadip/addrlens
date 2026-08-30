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


def _fmt_dist(m: int) -> str:
    """Format a metre threshold for tile rule text.

    ≥1000m becomes km ("1500" → "1.5km", "1000" → "1km"), else stays in
    metres with no space ("400" → "400m"). Kept spaceless to match the
    Young-Family rule style ("≥3 kitas within 400m").
    """
    if m >= 1000:
        return f"{m/1000:g}km"
    return f"{int(m)}m"


def _legend_for(key: str, th: dict) -> list:
    """Per-tile traffic-light legend for the in-card criteria strip.

    Returns [{"tier": "green|amber|red", "text": "..."}] in tier order so
    the frontend can render a three-line reference under every tile. Empty
    list = tile has no 3-band verdict (GESIx uses 5 quintiles, nightlife
    is numeric-only). Text kept short — legend rows sit in a compact strip
    with limited column width.
    """
    fd = _fmt_dist   # local alias for readability

    # Distance-to-nearest legends share the same three-string shape; several
    # Newcomer tiles collapse to it.
    def _dist_legend(green_m: int, amber_m: int) -> list:
        return [
            {"tier": TIER_GREEN, "text": f"≤{fd(green_m)} walk"},
            {"tier": TIER_AMBER, "text": f"≤{fd(amber_m)}"},
            {"tier": TIER_RED,   "text": f">{fd(amber_m)}"},
        ]

    # Count-in-radius legends (Intl food, Coworking) — same shape.
    def _count_legend(radius_m: int, green_c: int, amber_c: int) -> list:
        r = fd(radius_m)
        return [
            {"tier": TIER_GREEN, "text": f"≥{green_c} within {r}"},
            {"tier": TIER_AMBER, "text": f"{amber_c}–{green_c-1} within {r}"},
            {"tier": TIER_RED,   "text": f"<{amber_c} within {r}"},
        ]

    # -- Young Family ---------------------------------------------------
    if key == "kita":
        return [
            {"tier": TIER_GREEN, "text": f"≥{th['green_count']} kitas within {fd(th['green_m'])}"},
            {"tier": TIER_AMBER, "text": f"≥1 kita within {fd(th['amber_m'])}"},
            {"tier": TIER_RED,   "text": f"none within {fd(th['amber_m'])}"},
        ]
    if key == "playground":
        return [
            {"tier": TIER_GREEN, "text": f"≥1 within {fd(th['green_m'])}"},
            {"tier": TIER_AMBER, "text": f"{fd(th['green_m'])}–{fd(th['amber_m'])}"},
            {"tier": TIER_RED,   "text": f">{fd(th['amber_m'])}"},
        ]
    if key == "pediatrician":
        return [
            {"tier": TIER_GREEN, "text": f"≥1 within {fd(th['green_m'])}"},
            {"tier": TIER_AMBER, "text": f"{fd(th['green_m'])}–{fd(th['amber_m'])}"},
            {"tier": TIER_RED,   "text": f">{fd(th['amber_m'])}"},
        ]
    if key == "transit":
        return [
            {"tier": TIER_GREEN, "text": f"stop ≤{th['green_min']} min walk"},
            {"tier": TIER_AMBER, "text": f"stop ≤{th['amber_min']} min"},
            {"tier": TIER_RED,   "text": f">{th['amber_min']} min"},
        ]
    if key == "supermarket":
        return [
            {"tier": TIER_GREEN, "text": f"≥1 within {th['green_min']} min walk"},
            {"tier": TIER_AMBER, "text": f"within {th['amber_min']} min"},
            {"tier": TIER_RED,   "text": f">{th['amber_min']} min"},
        ]
    if key == "noise":
        return [
            {"tier": TIER_GREEN, "text": f"L_DEN ≤{th['green_db']} dB"},
            {"tier": TIER_AMBER, "text": f"{th['green_db']}–{th['amber_db']} dB"},
            {"tier": TIER_RED,   "text": f">{th['amber_db']} dB"},
        ]
    if key == "heat":
        return [
            {"tier": TIER_GREEN, "text": "keine / geringe"},
            {"tier": TIER_AMBER, "text": "mäßige / starke"},
            {"tier": TIER_RED,   "text": "sehr starke / extreme"},
        ]
    if key == "air":
        return [
            {"tier": TIER_GREEN, "text": f"NO₂ ≤{th['green_ugm3']} μg/m³"},
            {"tier": TIER_AMBER, "text": f"{th['green_ugm3']}–{th['amber_ugm3']} μg/m³"},
            {"tier": TIER_RED,   "text": f">{th['amber_ugm3']} μg/m³"},
        ]
    if key == "refuge":
        return [
            {"tier": TIER_GREEN, "text": f"quiet ≤{fd(th['green_quiet_m'])} OR crown ≥{th['green_crown_pct']}%"},
            {"tier": TIER_AMBER, "text": f"quiet ≤{fd(th['amber_quiet_m'])} OR crown ≥{th['amber_crown_pct']}%"},
            {"tier": TIER_RED,   "text": "neither"},
        ]

    # -- Newcomer -------------------------------------------------------
    if key == "buergeramt":
        return _dist_legend(th['green_m'], th['amber_m'])
    if key == "rail_transit":
        return [
            {"tier": TIER_GREEN, "text": f"S ≤{fd(th['sbahn_m'])} or U ≤{fd(th['ubahn_m'])}"},
            {"tier": TIER_AMBER, "text": f"rail ≤{fd(th['any_rail_m'])}"},
            {"tier": TIER_RED,   "text": f">{fd(th['any_rail_m'])}"},
        ]
    if key in ("tram_transit", "bus_transit", "english_clinic",
               "language_school", "library", "packstation", "wochenmarkt"):
        return _dist_legend(th['green_m'], th['amber_m'])
    if key == "intl_food":
        return _count_legend(th['radius_m'], th['green_count'], th['amber_count'])
    if key == "coworking":
        return _count_legend(th['radius_m'], th['green_count'], th['amber_count'])

    # nightlife_density (numeric-only) + gesix / gesix_newcomer (5-quintile)
    # don't fit a 3-band legend — skip.
    return []


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


def _shape_gesix(cfg, index, lat: float, lon: float, *,
                 card_key: str = "gesix",
                 label: str = "Neighbourhood profile") -> dict:
    """Shape-only GESIx tile. No tier badge, no numeric on face.
    Face renders label + one-line hint; modal renders the 5-segment
    quintile bar (frontend responsibility). Metadata carries the raw
    GESIx attributes; the insight template consumes them via
    _ctx_gesix in card_insight.py.

    Used by both the Young Family and Newcomer lenses — the caller
    controls `card_key` and `label` so the insight-template dispatcher
    can route by tile key.

    `cfg` is required so that `sources` resolves to the full licence text
    string from cfg.attribution rather than the bare dataset key "gesix".
    """
    g = index.gesix_at(lon, lat) if hasattr(index, "gesix_at") else None
    g = g or {}
    # Quintile → tier verdict (5-band GESIx socioeconomic index).
    # GESIx convention: quintile 1 = TOP 20% (most advantaged Planungsraum),
    # quintile 5 = BOTTOM 20%.  Rank is ascending on advantage — rank 1 is
    # the top-scoring Planungsraum, rank N the lowest.  The modal's
    # 5-segment bar already renders leftmost = "Top 20%" and maps segments
    # 1-2 green · 3 amber · 4-5 red; the tile-face gem must agree.
    _q = g.get("quintile_5")
    if _q == 1 or _q == 2:
        tier = TIER_GREEN
    elif _q == 3:
        tier = TIER_AMBER
    elif _q == 4 or _q == 5:
        tier = TIER_RED
    else:
        tier = TIER_UNKNOWN
    return {
        "key":      card_key,
        "label":    label,
        "icon":     "gesix",
        "tier":     tier,
        "rule":     "socioeconomic band of this Planungsraum · tap for detail",
        "numeric":  "",
        "caveat":   "",
        "features": [],
        "metadata": {"gesix": g},
        "sources":  [s for s in [cfg.attribution.get("gesix")] if s],
    }


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
        # Spec E — Newcomer lens
        # The Bürgeramt tile cites the BOD attribution string. The other
        # public-admin office data (Finanzamt / Standesamt / LEA /
        # Arbeitsagentur) is surfaced via the raw-view Others tab through
        # `app.core.others_admin.build`; its provenance is composed there.
        "buergeramt":     [attr.get("buergeramt")],
        # Transit uses the same VBB attribution as the YF transit tile.
        # OSM buckets cite Geofabrik; no separate attribution key in berlin.py
        # so we inline the standard ODbL line (ponytail: add per-key entries
        # to attribution once the snapshot source is pinned per-city).
        "rail_transit":    [attr.get("sbahn"), attr.get("ubahn")],
        "tram_transit":    [attr.get("tram")],
        "bus_transit":     ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "intl_food":       ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "coworking":       ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "english_clinic":  ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "language_school": ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "library":         ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "packstation":     ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "wochenmarkt":     ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "gesix_newcomer":  [attr.get("gesix")],
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
    # Cap the feature list at the tile's amber walk budget. Nearest-per-
    # modality can otherwise surface a modality with zero coverage in the
    # neighbourhood (e.g. Emser Str.: nearest Tram is S+U Warschauer Str.
    # 4 km away), which contradicts the tile's own rule ("≥1 stop within
    # 5 min stroller walk"). Tier is still min(walk_min) over the filtered
    # list, so a nearby Bus keeps a legitimately green verdict.
    _amber_min = thresholds["transit"]["amber_min"]
    _transit_feats = [f for f in _transit_feats
                      if f.get("walk_min") is not None
                      and f["walk_min"] <= _amber_min]
    # Dedup platform pairs that share a station name across modalities.
    # At S+U hubs (S+U Alexanderplatz, S+U Yorckstr., …) the nearest S-Bahn
    # and nearest U-Bahn resolve to the same physical station; VBB / BOD
    # tram also stores each direction as its own point ("… -> Stadt" /
    # "… -> Land"). Without dedup the UI card lists identical station
    # names twice. Collapse onto the closest hit per base name (partition
    # off the " -> DIR" suffix) and join modalities with " · " so the
    # single row still surfaces every mode the station serves.
    _clusters: dict = {}
    for _f in _transit_feats:
        _base = _f.get("name", "").partition(" -> ")[0].strip()
        if not _base:
            continue
        _entry = _clusters.get(_base)
        if _entry is None:
            _clusters[_base] = {**_f, "name": _base}
            continue
        _new = (_f.get("modality") or "").strip()
        if _new and _new not in (_entry.get("modality") or "").split(" · "):
            _existing = _entry.get("modality") or ""
            _entry["modality"] = f"{_existing} · {_new}" if _existing else _new
    _transit_feats = sorted(_clusters.values(),
                            key=lambda x: x.get("walk_min", 10**9))

    # Supermarkets — OSM-only; take nearest first from amenities bucket.
    _sm_block = (amenities or {}).get("supermarkets") or {}
    _sm_items = _sm_block.get("items") or []
    _sm_error = bool(_sm_block.get("error") or _sm_block.get("_error"))
    _sm_feats = [f for f in (_shape_supermarket(o) for o in _sm_items) if f]
    _sm_feats.sort(key=lambda x: x.get("walk_min", 10**9))

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
            "legend":  _legend_for(key, thresholds.get(key, {}) or {}),
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
        else:
            # noise, heat, air — aggregate readings, no per-feature list.
            # Attach the raw reading on metadata so the AI-insight route can
            # send structured facts to the LLM instead of a formatted string.
            tile["features"] = []
            if key == "noise":
                tile["metadata"] = {"l_den": (noise or {}).get("l_den"),
                                     "l_night": (noise or {}).get("l_night")}
            elif key == "heat":
                tile["metadata"] = {"day_class": (heat or {}).get("day_class"),
                                     "night_class": (heat or {}).get("night_class")}
            elif key == "air":
                tile["metadata"] = {"no2_ugm3": (air or {}).get("no2_ugm3")}
        tiles.append(tile)
        # GESIx shape-only tile follows supermarket in the original tile order.
        # Built via the shared helper so the Newcomer lens can reuse the same
        # logic with a different card_key.
        if key == "supermarket":
            tiles.append(_shape_gesix(cfg, index, lat, lon, card_key="gesix",
                                      label=tile_meta["gesix"][0]))

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }


# ======================================================================== #
# Spec E — Newcomer Lens (Task 4)                                          #
# Pure tier functions + composer.  No I/O; all data flows through Index.   #
# ======================================================================== #


def _tile(key: str, label: str, icon: str, *,
          tier: str, rule: str, numeric: str = "",
          caveat: str = "", features: list = None,
          sources: list = None, metadata: dict = None) -> dict:
    """Lightweight Spec D tile dict builder.  Fills every mandatory key with a
    safe default so callers only supply the fields that vary.

    ponytail: no schema validation here — callers are responsible for correct
    types; a future Pydantic model could replace this at v2."""
    d = {
        "key":      key,
        "label":    label,
        "icon":     icon,
        "tier":     tier,
        "rule":     rule,
        "numeric":  numeric,
        "caveat":   caveat,
        "features": features if features is not None else [],
        "sources":  sources  if sources  is not None else [],
    }
    if metadata is not None:
        d["metadata"] = metadata
    return d


def _shape_osm_feature(o: dict) -> Optional[dict]:
    """Shape an OSM local snapshot entry into the newcomer feature dict.
    Items from OsmLocalCache.near() carry: lat, lon, name (optional), tags
    (dict), distance_m (added by .near()), source='osm'.  Required: lat,
    lon, distance_m — name falls back to the amenity tag."""
    t = o.get("tags") or {}
    name = (o.get("name") or t.get("name") or
            t.get("amenity") or t.get("shop") or
            t.get("office") or "").strip()
    d = o.get("distance_m")
    # Build address from addr:* tags when present.
    street = (t.get("addr:street") or "").strip()
    hnr    = (t.get("addr:housenumber") or "").strip()
    plz    = (t.get("addr:postcode") or "").strip()
    city   = (t.get("addr:city") or "").strip()
    addr_l = f"{street} {hnr}".strip()
    addr_r = f"{plz} {city}".strip()
    address = ", ".join(p for p in [addr_l, addr_r] if p)
    r = _prune({
        "name":       name,
        "lat":        o.get("lat"),
        "lon":        o.get("lon"),
        "distance_m": d,
        "address":    address,
        "phone":      (t.get("phone") or t.get("contact:phone") or "").strip(),
        "website":    (t.get("website") or t.get("contact:website") or "").strip(),
        "hours":      (t.get("opening_hours") or "").strip(),
        "walk_min":   round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _tier_buergeramt_newcomer(features: list, th: dict) -> dict:
    """Newcomer Bürgeramt tile — distance-to-nearest logic.

    Thresholds (metres, inclusive on greener side):
      green_m  ≤ 1500m  → within a 15-minute walk
      amber_m  ≤ 3000m  → reachable but you'll need transit
      >  3000m           → cross-district trip required

    `features` is the pre-shaped & distance-sorted list from
    index.buergeramt_near() — dicts with {name, lat, lon, distance_m, ...}.

    Sources string is added by the composer via _sources_for.
    """
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no Bürgeramt within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"Bürgeramt ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"Bürgeramt ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no Bürgeramt within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to {nearest['name']}"}


def _tier_rail_transit(features: list, th: dict) -> dict:
    """Newcomer Rail-Transit tile — heavy-rail (S-Bahn + U-Bahn) only.
    Tram is scored by _tier_tram_transit as its own tile.

    `features`: list of dicts with {name, lat, lon, distance_m, mode}
    where mode is one of 'S' or 'U' (comma-joined at S+U hubs).
    Sorted ascending by distance_m.  Built by newcomer_lens() by
    scanning index.sbahn + index.ubahn and tagging each with its mode.

    Green conditions (inclusive on the greener side):
      • any S-Bahn ≤ sbahn_m (800 m), OR
      • any U-Bahn ≤ ubahn_m (500 m)
    Amber:
      • any S/U rail ≤ any_rail_m (1 200 m)
    Red:
      • nothing within any_rail_m.
    """
    green_rule = (f"S-Bahn ≤{_fmt_dist(th['sbahn_m'])} OR "
                  f"U-Bahn ≤{_fmt_dist(th['ubahn_m'])}")
    amber_rule = f"rail ≤{_fmt_dist(th['any_rail_m'])}"
    red_rule   = f"no rail within {_fmt_dist(th['any_rail_m'])}"
    if not features:
        return {"tier": TIER_RED, "rule": red_rule, "numeric": ""}
    # Green — S or U within their respective limits.
    for f in features:
        d = f["distance_m"]
        mode = f.get("mode", "")
        if "S" in mode and d <= th["sbahn_m"]:
            return {"tier": TIER_GREEN, "rule": green_rule,
                    "numeric": f"{int(d)} m to S-Bahn {f['name']}"}
        if "U" in mode and d <= th["ubahn_m"]:
            return {"tier": TIER_GREEN, "rule": green_rule,
                    "numeric": f"{int(d)} m to U-Bahn {f['name']}"}
    # Amber — any S/U rail within any_rail_m.
    for f in features:
        if f["distance_m"] <= th["any_rail_m"]:
            mode_label = {"S": "S-Bahn", "U": "U-Bahn"}.get(
                f.get("mode", "")[:1], "Rail")
            return {"tier": TIER_AMBER, "rule": amber_rule,
                    "numeric": f"{int(f['distance_m'])} m to {mode_label} {f['name']}"}
    # Red.
    return {"tier": TIER_RED, "rule": red_rule, "numeric": ""}


def _tier_tram_transit(features: list, th: dict) -> dict:
    """Newcomer Tram-Transit tile — distance-to-nearest tram stop.

    Same tier shape as Rail Transit but a single-mode source.
    `features`: list of dicts with {name, lat, lon, distance_m},
    sorted ascending by distance_m. Thresholds in metres."""
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no tram within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"tram stop ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"tram stop ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no tram within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to Tram {nearest['name']}"}


def _tier_bus_transit(features: list, th: dict) -> dict:
    """Newcomer Bus-Transit tile — distance-to-nearest bus stop.

    Same tier shape as Tram Transit but drawn from the OSM `transit`
    bucket filtered to bus-tagged items. Thresholds in metres."""
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no bus within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"bus stop ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"bus stop ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no bus within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to Bus {nearest['name']}"}


def _tier_intl_food(features: list, th: dict) -> dict:
    """Count-based tier for international food & grocers within radius_m.
    green_count / amber_count are inclusive lower bounds."""
    n = len(features)
    r = _fmt_dist(th['radius_m'])
    if n >= th["green_count"]:
        tier = TIER_GREEN
        rule = f"≥{th['green_count']} intl food spots within {r}"
    elif n >= th["amber_count"]:
        tier = TIER_AMBER
        rule = f"{th['amber_count']}–{th['green_count']-1} intl food spots within {r}"
    else:
        tier = TIER_RED
        rule = f"<{th['amber_count']} intl food spots within {r}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{n} international spots within {th['radius_m']} m walk"}


def _tier_coworking(features: list, th: dict) -> dict:
    """Count-based tier for coworking spaces + Wi-Fi cafés within radius_m."""
    n = len(features)
    r = _fmt_dist(th['radius_m'])
    if n >= th["green_count"]:
        tier = TIER_GREEN
        rule = f"≥{th['green_count']} coworking / laptop cafés within {r}"
    elif n >= th["amber_count"]:
        tier = TIER_AMBER
        rule = f"{th['amber_count']}–{th['green_count']-1} coworking / laptop cafés within {r}"
    else:
        tier = TIER_RED
        rule = f"<{th['amber_count']} coworking / laptop cafés within {r}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{n} remote-work spots within {th['radius_m']} m"}


def _tier_english_clinic(features: list, th: dict) -> dict:
    """Distance-to-nearest English-tagged medical practice.

    Thresholds (metres, inclusive on greener side):
      green_m  ≤ 1200m  → walking distance
      amber_m  ≤ 3000m  → short transit ride
      > 3000m            → telemedicine territory

    ponytail: OSM 'language:en=yes' tagging is community-maintained;
    inner-district coverage is good, outer Berlin may under-report.
    The caveat string is surfaced from cfg.newcomer_lens tile config.
    """
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no English clinic within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"English clinic ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"English clinic ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no English clinic within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to {nearest['name']}"}


def _tier_language_school(features: list, th: dict) -> dict:
    """Distance-to-nearest language school (VHS + private Sprachschulen).

    Thresholds (metres, inclusive on greener side):
      green_m  ≤ 1500m  → walkable evening class
      amber_m  ≤ 3500m  → one S/U hop to class
      > amber_m         → learning becomes a logistics problem
    """
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no German school within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"German school ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"German school ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no German school within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to {nearest['name']}"}


def _tier_library(features: list, th: dict) -> dict:
    """Distance-to-nearest public library (VÖBB + Uni libraries).

    Thresholds (metres, inclusive on greener side):
      green_m  ≤ 1000m  → walk-in comfort zone
      amber_m  ≤ 2500m  → still a habit-forming distance
      > amber_m         → not a spontaneous stop
    """
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no library within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"library ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"library ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no library within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to {nearest['name']}"}


def _tier_packstation(features: list, th: dict) -> dict:
    """Distance-to-nearest parcel pickup point (DHL Packstation + Post branch).

    Thresholds (metres, inclusive on greener side):
      green_m  ≤ 400m   → daily-carry radius
      amber_m  ≤ 1000m  → tolerable evening detour
      > amber_m         → parcel pickup becomes a chore
    """
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no Packstation within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"Packstation ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"Packstation ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no Packstation within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to {nearest['name']}"}


def _tier_nightlife_density(features: list, th: dict) -> dict:
    """Numeric-only nightlife density tile — always tier=unknown.

    The same feature (dense bars / clubs / pubs) is a positive for one
    newcomer and a negative for another; we present the number, not a
    verdict.  The noise tile carries the sound-level side of the same
    signal for anyone who cares about sleep.

    `th` is expected to be an empty dict; radius is fixed at 1 km via
    the composer.
    """
    n = len(features)
    if n == 0:
        return {"tier": TIER_UNKNOWN,
                "rule": "no bars / clubs within 1km",
                "numeric": ""}
    return {"tier": TIER_UNKNOWN,
            "rule": f"{n} bars / clubs within 1km · numeric only",
            "numeric": f"{n} bars / clubs / pubs within 1 km"}


def _tier_wochenmarkt(features: list, th: dict) -> dict:
    """Distance-to-nearest permitted weekly market (Wochenmarkt).

    Thresholds (metres, inclusive on greener side):
      green_m  ≤ 800m   → weekly-walk habit distance
      amber_m  ≤ 2000m  → a short bike or tram
      > amber_m         → not a weekly ritual

    ponytail: OSM/BOD closure lag can be 6-12 months; a "green" tile at an
    address next to a recently-closed market will look wrong for a season.
    Caveat surfaced via LensTileConfig.caveat.
    """
    if not features:
        return {"tier": TIER_RED,
                "rule": f"no Wochenmarkt within {_fmt_dist(th['amber_m'])}",
                "numeric": ""}
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier = TIER_GREEN
        rule = f"Wochenmarkt ≤{_fmt_dist(th['green_m'])} walk"
    elif d <= th["amber_m"]:
        tier = TIER_AMBER
        rule = f"Wochenmarkt ≤{_fmt_dist(th['amber_m'])}"
    else:
        tier = TIER_RED
        rule = f"no Wochenmarkt within {_fmt_dist(th['amber_m'])}"
    return {"tier": tier, "rule": rule,
            "numeric": f"{int(d)} m to {nearest['name']}"}


def newcomer_lens(cfg, index, lon: float, lat: float, *,
                  amenities: dict | None = None) -> dict:
    """Assemble the 6-tile Newcomer lens block.

    Reads only pre-loaded Index state — no live fetch on the hot path.
    Each tier function is a small pure translation from feature list +
    thresholds to a tier dict; the composer wraps each in the Spec D
    tile shape and resolves provenance strings from cfg.attribution.

    Args follow the project-wide (lon, lat) convention — same as
    young_family_lens.

    Tile order (fixed): buergeramt, rail_transit, tram_transit,
    bus_transit, intl_food, coworking, english_clinic, gesix_newcomer.

    `amenities` is the OSM buckets dict from amenities_near() — only the
    "transit" bucket is consumed here (nearest bus-tagged stop for the
    bus_transit tile). Passed as kwarg so tests / phase3 parity checks
    can call this without an amenities snapshot.
    """
    assert -60 <= lat <= 60, f"lat out of range: {lat}"
    assert -180 <= lon <= 180, f"lon out of range: {lon}"
    lens = cfg.newcomer_lens
    th         = {t.key: t.thresholds for t in lens.tiles}
    tile_meta  = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    # -- Bürgeramt: BOD-first (preloaded via buergeramt_near) ----------------
    # Berlin has a live BOD ServicePortal feed wired in Spec B; OSM bucket
    # is the v2-cities fallback only.  BOD-first per Global Constraints.
    buergeramt_raw = index.buergeramt_near(lon, lat, 5000)
    buergeramt_feats = [f for f in (_shape_office(o) for o in buergeramt_raw) if f]

    # -- Rail (S+U) from preloaded VBB+BOD lists -----------------------------
    # ponytail: No vbb_query() method exists; access per-modality lists
    # directly.  Upgrade path: extract vbb_query() on Index when a third
    # lens needs S/U unified access.
    def _cluster_by_base(raw: list) -> list:
        """Dedup platform pairs sharing a station name. Two effects to
        collapse: (a) VBB / BOD tram stores each direction as its own
        point ("Freienwalder Str. -> Stadt" / "-> Land"); (b) at S+U
        hubs (S+U Hermannstr., S+U Alexanderplatz…) VBB stores S-Bahn
        and U-Bahn platforms as separate points with identical base
        names. Cluster by base_name only. Keep nearest hit; join
        distinct modes with "," so the SPA can map to labels; union
        the direction suffixes."""
        clusters: dict = {}
        for p in raw:
            base, _sep, direction = p["name"].partition(" -> ")
            base = base.strip()
            direction = direction.strip()
            entry = clusters.get(base)
            if entry is None:
                entry = {**p, "name": base, "directions": []}
                clusters[base] = entry
            existing_modes = entry.get("mode", "").split(",")
            if p.get("mode") and p["mode"] not in existing_modes:
                entry["mode"] = ",".join(
                    [m for m in existing_modes if m] + [p["mode"]])
            if direction and direction not in entry["directions"]:
                entry["directions"].append(direction)
        return sorted(clusters.values(), key=lambda x: x["distance_m"])

    _rail_raw = []
    _rail_cap = th["rail_transit"]["any_rail_m"] * 2  # wide pre-filter
    for mode_tag, points in (("S", index.sbahn), ("U", index.ubahn)):
        for p in points:
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= _rail_cap:
                _rail_raw.append({**p, "distance_m": round(d), "mode": mode_tag})
    _rail_raw.sort(key=lambda x: x["distance_m"])
    rail_feats = _cluster_by_base(_rail_raw)

    # -- Tram from preloaded VBB tram list -----------------------------------
    _tram_raw = []
    _tram_cap = th["tram_transit"]["amber_m"] * 2  # wide pre-filter
    for p in index.tram:
        d = haversine_m(lon, lat, p["lon"], p["lat"])
        if d <= _tram_cap:
            _tram_raw.append({**p, "distance_m": round(d), "mode": "T"})
    _tram_raw.sort(key=lambda x: x["distance_m"])
    tram_feats = _cluster_by_base(_tram_raw)

    # -- Bus from OSM `transit` bucket (bus-tagged only) --------------------
    # amenities_near() is called by the /api/lookup handler and passed in;
    # newcomer_lens tolerates its absence (returns [] → red tile).
    _tr_block = (amenities or {}).get("transit") or {}
    _tr_items = _tr_block.get("items") or []
    _bus_items = [it for it in _tr_items
                  if (it.get("tags") or {}).get("bus") == "yes"
                  or (it.get("tags") or {}).get("highway") == "bus_stop"]
    _bus_items.sort(key=lambda x: x.get("distance_m", 10**9))
    bus_feats = []
    for it in _bus_items:
        d = it.get("distance_m")
        name = (it.get("name") or "").strip()
        if d is None or not name:
            continue
        bus_feats.append({"name": name,
                          "lat": it.get("lat"), "lon": it.get("lon"),
                          "distance_m": round(d)})

    # -- OSM local buckets: intl_food, coworking, english_clinic -------------
    oc = getattr(index, "osm_local", None)

    def _osm_near(bucket: str, radius_m: int) -> list:
        """Query OsmLocalCache or return [] when the cache is absent."""
        if oc is None:
            return []
        return oc.near(bucket, lon, lat, radius_m)

    intl_food_raw     = _osm_near("intl_food",     th["intl_food"]["radius_m"])
    coworking_raw     = _osm_near("coworking",      th["coworking"]["radius_m"])
    english_clinic_raw = _osm_near("english_clinic", 3500)
    # 4 new distance-to-nearest tiles.  Radius fetched wide (~amber×1.5)
    # so the tile can honestly render "no match" when nothing qualifies.
    language_school_raw = _osm_near("language_school", th["language_school"]["amber_m"] + 1500)
    library_raw         = _osm_near("library",         th["library"]["amber_m"] + 1500)
    packstation_raw     = _osm_near("packstation",     th["packstation"]["amber_m"] + 500)
    wochenmarkt_raw     = _osm_near("wochenmarkt",     th["wochenmarkt"]["amber_m"] + 1000)
    # Nightlife density is numeric-only (no verdict) — fixed 1 km radius.
    nightlife_raw       = _osm_near("nightlife",       1000)

    intl_food_feats     = [f for f in (_shape_osm_feature(o) for o in intl_food_raw)     if f]
    coworking_feats     = [f for f in (_shape_osm_feature(o) for o in coworking_raw)     if f]
    english_clinic_feats = [f for f in (_shape_osm_feature(o) for o in english_clinic_raw) if f]
    language_school_feats = [f for f in (_shape_osm_feature(o) for o in language_school_raw) if f]
    library_feats       = [f for f in (_shape_osm_feature(o) for o in library_raw)       if f]
    packstation_feats   = [f for f in (_shape_osm_feature(o) for o in packstation_raw)   if f]
    wochenmarkt_feats   = [f for f in (_shape_osm_feature(o) for o in wochenmarkt_raw)   if f]
    nightlife_feats     = [f for f in (_shape_osm_feature(o) for o in nightlife_raw)     if f]

    # -- Tier computations ---------------------------------------------------
    results = [
        ("buergeramt",     _tier_buergeramt_newcomer(buergeramt_feats, th["buergeramt"])),
        ("rail_transit",   _tier_rail_transit(rail_feats,              th["rail_transit"])),
        ("tram_transit",   _tier_tram_transit(tram_feats,              th["tram_transit"])),
        ("bus_transit",    _tier_bus_transit(bus_feats,                th["bus_transit"])),
        ("intl_food",      _tier_intl_food(intl_food_feats,            th["intl_food"])),
        ("coworking",      _tier_coworking(coworking_feats,            th["coworking"])),
        ("english_clinic", _tier_english_clinic(english_clinic_feats,  th["english_clinic"])),
        ("language_school", _tier_language_school(language_school_feats, th["language_school"])),
        ("library",        _tier_library(library_feats,                th["library"])),
        ("packstation",    _tier_packstation(packstation_feats,        th["packstation"])),
        ("wochenmarkt",    _tier_wochenmarkt(wochenmarkt_feats,        th["wochenmarkt"])),
        ("nightlife_density", _tier_nightlife_density(nightlife_feats, th["nightlife_density"])),
    ]

    tiles = []
    feat_map = {
        "buergeramt":      buergeramt_feats,
        "rail_transit":    [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                              "distance_m": f["distance_m"], "mode": f["mode"],
                              "walk_min": round(_walk_minutes(f["distance_m"])),
                              "directions": f.get("directions", [])}
                             for f in rail_feats[:10]],
        "tram_transit":    [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                              "distance_m": f["distance_m"], "mode": "T",
                              "walk_min": round(_walk_minutes(f["distance_m"])),
                              "directions": f.get("directions", [])}
                             for f in tram_feats[:10]],
        "bus_transit":     [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                              "distance_m": f["distance_m"], "mode": "B",
                              "walk_min": round(_walk_minutes(f["distance_m"]))}
                             for f in bus_feats[:10]],
        "intl_food":       intl_food_feats[:10],
        "coworking":       coworking_feats[:10],
        "english_clinic":  english_clinic_feats[:10],
        "language_school": language_school_feats[:10],
        "library":         library_feats[:10],
        "packstation":     packstation_feats[:10],
        "wochenmarkt":     wochenmarkt_feats[:10],
        "nightlife_density": nightlife_feats[:10],
    }

    for key, res in results:
        label, icon, caveat = tile_meta[key]
        # Numeric-only tiles are tier=UNKNOWN by design; _sources_for()
        # returns [] for unknown, which would drop the OSM attribution for
        # a count that IS a real fact.  Override for these keys so the
        # citation still renders.
        if key == "nightlife_density":
            sources = ["© OpenStreetMap contributors (ODbL) via Geofabrik"]
        else:
            sources = _sources_for(cfg, key, res["tier"])
        tile = {
            "key":      key,
            "label":    label,
            "icon":     icon,
            "tier":     res["tier"],
            "rule":     res["rule"],
            "numeric":  res["numeric"],
            "caveat":   caveat,
            "features": feat_map.get(key, []),
            "sources":  sources,
            "legend":   _legend_for(key, th.get(key, {}) or {}),
        }
        tiles.append(tile)

    # GESIx shape-only tile last.
    tiles.append(_shape_gesix(cfg, index, lat, lon, card_key="gesix_newcomer",
                              label=tile_meta["gesix_newcomer"][0]))

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

    # -- _walk_minutes sanity (still exercised by newcomer + shape.walk_min).
    assert _walk_minutes(0)   == 0.0
    assert _walk_minutes(62)  == 1.0
    assert abs(_walk_minutes(930) - 15.0) < 1e-9

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

    # -- _shape_gesix: default key + newcomer key (Task 3 selfcheck) ---------
    class _StubCfg:
        attribution = {"gesix": "Berlin Geoportal — GESIx 2022 · dl-de/by-2-0"}

    class _StubGesix:
        def gesix_at(self, lon, lat):
            return {"plr_name": "X", "quintile_5": 3, "rang": 200, "total": 447}

    _sg = _shape_gesix(_StubCfg(), _StubGesix(), 52.5, 13.4)
    assert _sg["key"]  == "gesix", _sg
    # Quintile 3 → amber verdict (mid-band).
    assert _sg["tier"] == TIER_AMBER, _sg
    assert _sg["metadata"]["gesix"]["quintile_5"] == 3, _sg
    assert _sg["icon"]     == "gesix"
    assert _sg["label"]    == "Neighbourhood profile"
    assert _sg["features"] == []
    assert _sg["caveat"]   == ""
    assert _sg["sources"]  == ["Berlin Geoportal — GESIx 2022 · dl-de/by-2-0"]
    assert _sg["sources"]  != ["gesix"]      # regression guard

    _sg2 = _shape_gesix(_StubCfg(), _StubGesix(), 52.5, 13.4,
                        card_key="gesix_newcomer",
                        label="Neighbourhood profile")
    assert _sg2["key"]  == "gesix_newcomer", _sg2
    assert _sg2["tier"] == TIER_AMBER, _sg2
    assert _sg2["metadata"]["gesix"]["quintile_5"] == 3
    assert _sg2["sources"] == ["Berlin Geoportal — GESIx 2022 · dl-de/by-2-0"]

    # Quintile boundary sweep — Q1,Q2 green (top bands) · Q3 amber · Q4,Q5 red
    # (bottom bands).  Convention matches modal's leftmost=Top segment.
    class _StubGQ:
        def __init__(self, q): self.q = q
        def gesix_at(self, lon, lat):
            return {"plr_name": "X", "quintile_5": self.q, "rang": 100, "total": 447}
    assert _shape_gesix(_StubCfg(), _StubGQ(1), 52.5, 13.4)["tier"] == TIER_GREEN
    assert _shape_gesix(_StubCfg(), _StubGQ(2), 52.5, 13.4)["tier"] == TIER_GREEN
    assert _shape_gesix(_StubCfg(), _StubGQ(3), 52.5, 13.4)["tier"] == TIER_AMBER
    assert _shape_gesix(_StubCfg(), _StubGQ(4), 52.5, 13.4)["tier"] == TIER_RED
    assert _shape_gesix(_StubCfg(), _StubGQ(5), 52.5, 13.4)["tier"] == TIER_RED

    # None from gesix_at → empty metadata dict, tier unknown, still well-formed
    class _StubGesixNone:
        def gesix_at(self, lon, lat): return None
    _sg_none = _shape_gesix(_StubCfg(), _StubGesixNone(), 52.5, 13.4)
    assert _sg_none["key"]          == "gesix"
    assert _sg_none["tier"]         == TIER_UNKNOWN
    assert _sg_none["metadata"]     == {"gesix": {}}
    assert _sg_none["features"]     == []

    print("scorer.py: _shape_gesix selfcheck OK")

    # ===================================================================== #
    # Task 4 — Newcomer tier functions + composer selfchecks               #
    # ===================================================================== #

    # _tile helper — mandatory keys always present, metadata only when given.
    _t0 = _tile("k", "L", "i", tier="green", rule="r")
    assert _t0["key"] == "k" and _t0["tier"] == "green"
    assert _t0["features"] == [] and _t0["sources"] == []
    assert "metadata" not in _t0
    _t1 = _tile("k", "L", "i", tier="green", rule="r",
                metadata={"x": 1})
    assert "metadata" in _t1 and _t1["metadata"]["x"] == 1

    # _shape_osm_feature — well-formed and malformed inputs.
    _osm_ok = {"lat": 52.5, "lon": 13.4, "distance_m": 400, "source": "osm",
               "name": "Grocery X",
               "tags": {"addr:street": "Bergmannstraße", "addr:housenumber": "5",
                        "opening_hours": "Mo-Su 08:00-20:00"}}
    _so = _shape_osm_feature(_osm_ok)
    assert _so is not None
    assert _so["name"] == "Grocery X"
    assert _so["distance_m"] == 400
    assert _so["hours"] == "Mo-Su 08:00-20:00"
    assert isinstance(_so["walk_min"], int)
    # Missing lat → None
    assert _shape_osm_feature({"lon": 13.4, "distance_m": 100}) is None
    # Empty name falls back to amenity tag
    _osm_noname = {"lat": 52.5, "lon": 13.4, "distance_m": 200, "source": "osm",
                   "tags": {"amenity": "restaurant"}}
    assert _shape_osm_feature(_osm_noname)["name"] == "restaurant"

    # -- _tier_buergeramt_newcomer -------------------------------------------
    _TN = {t.key: t.thresholds for t in _CFG_YF.newcomer_lens.tiles}

    _B_f = lambda d: [{"name": "BA-Test", "lat": 52.5, "lon": 13.4,
                        "distance_m": d}]
    # At exactly green boundary → green (inclusive).
    assert _tier_buergeramt_newcomer(_B_f(1500),    _TN["buergeramt"])["tier"] == TIER_GREEN
    # One metre beyond → amber.
    assert _tier_buergeramt_newcomer(_B_f(1501),    _TN["buergeramt"])["tier"] == TIER_AMBER
    assert _tier_buergeramt_newcomer(_B_f(3000),    _TN["buergeramt"])["tier"] == TIER_AMBER
    # One metre beyond amber → red.
    assert _tier_buergeramt_newcomer(_B_f(3001),    _TN["buergeramt"])["tier"] == TIER_RED
    # Empty list → red (no data).
    assert _tier_buergeramt_newcomer([],            _TN["buergeramt"])["tier"] == TIER_RED

    # Numeric carries distance + name for green/amber/red (non-empty).
    _bn = _tier_buergeramt_newcomer(_B_f(1000), _TN["buergeramt"])
    assert "1000" in _bn["numeric"] and "BA-Test" in _bn["numeric"]

    # -- _tier_rail_transit ---------------------------------------------------
    _TRN = _TN["rail_transit"]

    def _tr_f(mode, d):
        return [{"name": "Ost", "lat": 52.5, "lon": 13.4,
                 "distance_m": d, "mode": mode}]

    # S-Bahn ≤ 800 m → green.
    assert _tier_rail_transit(_tr_f("S", 800),  _TRN)["tier"] == TIER_GREEN
    # S-Bahn 801 m → not green; then amber if ≤ 1200 m.
    assert _tier_rail_transit(_tr_f("S", 801),  _TRN)["tier"] == TIER_AMBER
    # U-Bahn ≤ 500 m → green.
    assert _tier_rail_transit(_tr_f("U", 500),  _TRN)["tier"] == TIER_GREEN
    # U-Bahn 501 m → not green U; amber (within any_rail_m=1200).
    assert _tier_rail_transit(_tr_f("U", 501),  _TRN)["tier"] == TIER_AMBER
    # Empty → red.
    assert _tier_rail_transit([],               _TRN)["tier"] == TIER_RED

    # -- _tier_tram_transit ---------------------------------------------------
    _TTM = _TN["tram_transit"]
    def _tm_f(d):
        return [{"name": "TramStop", "lat": 52.5, "lon": 13.4, "distance_m": d}]
    assert _tier_tram_transit(_tm_f(500),  _TTM)["tier"] == TIER_GREEN  # green_m=500 inclusive
    assert _tier_tram_transit(_tm_f(501),  _TTM)["tier"] == TIER_AMBER
    assert _tier_tram_transit(_tm_f(1000), _TTM)["tier"] == TIER_AMBER  # amber_m=1000 inclusive
    assert _tier_tram_transit(_tm_f(1001), _TTM)["tier"] == TIER_RED
    assert _tier_tram_transit([],          _TTM)["tier"] == TIER_RED

    # -- _tier_bus_transit ----------------------------------------------------
    _TBS = _TN["bus_transit"]
    def _bs_f(d):
        return [{"name": "BusStop", "lat": 52.5, "lon": 13.4, "distance_m": d}]
    assert _tier_bus_transit(_bs_f(300),  _TBS)["tier"] == TIER_GREEN   # green_m=300 inclusive
    assert _tier_bus_transit(_bs_f(301),  _TBS)["tier"] == TIER_AMBER
    assert _tier_bus_transit(_bs_f(600),  _TBS)["tier"] == TIER_AMBER   # amber_m=600 inclusive
    assert _tier_bus_transit(_bs_f(601),  _TBS)["tier"] == TIER_RED
    assert _tier_bus_transit([],          _TBS)["tier"] == TIER_RED

    # -- _tier_intl_food ------------------------------------------------------
    _TIF = _TN["intl_food"]
    _ff  = lambda n: [{"name": f"Shop{i}", "lat": 52.5, "lon": 13.4,
                        "distance_m": 100}      for i in range(n)]
    assert _tier_intl_food(_ff(6),  _TIF)["tier"] == TIER_GREEN   # green_count=6, inclusive
    assert _tier_intl_food(_ff(5),  _TIF)["tier"] == TIER_AMBER   # < green but ≥ amber_count=2
    assert _tier_intl_food(_ff(2),  _TIF)["tier"] == TIER_AMBER   # amber_count=2, inclusive
    assert _tier_intl_food(_ff(1),  _TIF)["tier"] == TIER_RED
    assert _tier_intl_food([],      _TIF)["tier"] == TIER_RED
    # Numeric always carries count + radius.
    _tn = _tier_intl_food(_ff(3), _TIF)
    assert "3" in _tn["numeric"] and str(_TIF["radius_m"]) in _tn["numeric"]

    # -- _tier_coworking -------------------------------------------------------
    _TCW = _TN["coworking"]
    _cf  = lambda n: [{"name": f"Desk{i}", "lat": 52.5, "lon": 13.4,
                        "distance_m": 200}      for i in range(n)]
    assert _tier_coworking(_cf(3), _TCW)["tier"] == TIER_GREEN    # green_count=3, inclusive
    assert _tier_coworking(_cf(2), _TCW)["tier"] == TIER_AMBER    # < green but ≥ amber_count=1
    assert _tier_coworking(_cf(1), _TCW)["tier"] == TIER_AMBER    # amber_count=1, inclusive
    assert _tier_coworking([],     _TCW)["tier"] == TIER_RED

    # -- _tier_english_clinic --------------------------------------------------
    _TEC = _TN["english_clinic"]
    _ef  = lambda d: [{"name": "Clinic", "lat": 52.5, "lon": 13.4,
                        "distance_m": d}]
    # green_m=1000, inclusive.
    assert _tier_english_clinic(_ef(1000),    _TEC)["tier"] == TIER_GREEN
    assert _tier_english_clinic(_ef(1001),    _TEC)["tier"] == TIER_AMBER
    assert _tier_english_clinic(_ef(3000),    _TEC)["tier"] == TIER_AMBER
    assert _tier_english_clinic(_ef(3001),    _TEC)["tier"] == TIER_RED
    assert _tier_english_clinic([],           _TEC)["tier"] == TIER_RED

    # -- _tier_language_school / library / packstation / wochenmarkt ---------
    _mkf = lambda d, name="X": [{"name": name, "lat": 52.5, "lon": 13.4, "distance_m": d}]
    _TLS = _TN["language_school"]
    assert _tier_language_school(_mkf(1500), _TLS)["tier"] == TIER_GREEN
    assert _tier_language_school(_mkf(1501), _TLS)["tier"] == TIER_AMBER
    assert _tier_language_school(_mkf(3500), _TLS)["tier"] == TIER_AMBER
    assert _tier_language_school(_mkf(3501), _TLS)["tier"] == TIER_RED
    assert _tier_language_school([],         _TLS)["tier"] == TIER_RED
    _TLB = _TN["library"]
    assert _tier_library(_mkf(1000), _TLB)["tier"] == TIER_GREEN
    assert _tier_library(_mkf(1001), _TLB)["tier"] == TIER_AMBER
    assert _tier_library(_mkf(2500), _TLB)["tier"] == TIER_AMBER
    assert _tier_library(_mkf(2501), _TLB)["tier"] == TIER_RED
    assert _tier_library([],         _TLB)["tier"] == TIER_RED
    _TPK = _TN["packstation"]
    assert _tier_packstation(_mkf(400),  _TPK)["tier"] == TIER_GREEN
    assert _tier_packstation(_mkf(401),  _TPK)["tier"] == TIER_AMBER
    assert _tier_packstation(_mkf(1000), _TPK)["tier"] == TIER_AMBER
    assert _tier_packstation(_mkf(1001), _TPK)["tier"] == TIER_RED
    assert _tier_packstation([],         _TPK)["tier"] == TIER_RED
    _TWM = _TN["wochenmarkt"]
    assert _tier_wochenmarkt(_mkf(800),  _TWM)["tier"] == TIER_GREEN
    assert _tier_wochenmarkt(_mkf(801),  _TWM)["tier"] == TIER_AMBER
    assert _tier_wochenmarkt(_mkf(2000), _TWM)["tier"] == TIER_AMBER
    assert _tier_wochenmarkt(_mkf(2001), _TWM)["tier"] == TIER_RED
    assert _tier_wochenmarkt([],         _TWM)["tier"] == TIER_RED

    # -- _tier_nightlife_density (numeric-only, always tier=unknown) ---------
    _TNL = _TN.get("nightlife_density", {})
    _r = _tier_nightlife_density([{"name": "Bar", "lat": 52.5, "lon": 13.4, "distance_m": 300}], _TNL)
    assert _r["tier"] == TIER_UNKNOWN, _r
    assert "1 bars / clubs / pubs within 1 km" in _r["numeric"], _r
    _r0 = _tier_nightlife_density([], _TNL)
    assert _r0["tier"] == TIER_UNKNOWN, _r0
    assert _r0["numeric"] == "", _r0
    assert "no bars" in _r0["rule"], _r0

    # -- newcomer_lens composer smoke test ------------------------------------
    from app.cities.berlin import BERLIN as _CFG_NL

    class _StubNLIdx:
        """Stub Index for newcomer_lens composer — returns empty for everything."""
        sbahn = []
        ubahn = []
        tram  = []
        osm_local = None   # will be replaced below

        def buergeramt_near(self, lon, lat, radius_m=5000):
            return []

        def gesix_at(self, lon, lat):
            return {"plr_name": "X", "quintile_5": 3, "rang": 200, "total": 447}

    _out = newcomer_lens(_CFG_NL, _StubNLIdx(), 13.4, 52.5)  # lon, lat — Berlin centre
    # Full envelope — canonical keys.
    assert all(k in _out for k in ("slug", "label", "audience", "tiles", "provenance")), \
        f"missing envelope keys: {sorted(_out)}"
    assert _out["slug"] == "newcomer"
    assert _out["label"] == "Newcomer"
    assert len(_out["tiles"]) == 13
    # Tile key order (plan-specified).
    _keys_nl = [t["key"] for t in _out["tiles"]]
    assert _keys_nl == ["buergeramt",
                        "rail_transit", "tram_transit", "bus_transit",
                        "intl_food", "coworking", "english_clinic",
                        "language_school", "library", "packstation", "wochenmarkt",
                        "nightlife_density",
                        "gesix_newcomer"], _keys_nl
    # Numeric-only nightlife tile: tier must be UNKNOWN even with features,
    # and sources must still cite OSM (override in composer).
    _nl_night = {t["key"]: t for t in _out["tiles"]}["nightlife_density"]
    assert _nl_night["tier"] == TIER_UNKNOWN, _nl_night
    assert any("OpenStreetMap" in s for s in _nl_night["sources"]), _nl_night["sources"]
    # gesix_newcomer now carries a quintile-based tier verdict.
    # Stub quintile_5=3 → amber.
    _by_nl = {t["key"]: t for t in _out["tiles"]}
    assert _by_nl["gesix_newcomer"]["tier"] == TIER_AMBER
    # All traffic-light tiles have mandatory Spec D keys.
    _spec_d_keys = {"key","label","icon","tier","rule","numeric","caveat","sources","features"}
    for t in _out["tiles"]:
        assert _spec_d_keys <= set(t.keys()), t

    # gesix_newcomer carries metadata.gesix.
    assert "metadata" in _by_nl["gesix_newcomer"]
    assert "gesix" in _by_nl["gesix_newcomer"]["metadata"]

    # sources uses attribution TEXT, not keys (regression guard from Task 3 fix).
    # _shape_gesix populates sources directly from cfg.attribution["gesix"] —
    # it does not route through _sources_for, so sources is non-empty even when
    # tier == "unknown".
    _nl_gesix_sources = _by_nl["gesix_newcomer"]["sources"]
    assert _nl_gesix_sources != ["gesix"] and _nl_gesix_sources != ["gesix_newcomer"], \
        f"sources must be attribution TEXT, not key: {_nl_gesix_sources}"
    assert any("GESIx" in s or "Senatsverwaltung" in s for s in _nl_gesix_sources), \
        f"gesix sources must cite attribution text: {_nl_gesix_sources}"
    # Confirm _sources_for resolves newcomer keys to text (not bare key strings).
    _src_chk = _sources_for(_CFG_NL, "gesix_newcomer", "green")
    assert _src_chk != ["gesix_newcomer"] and _src_chk != ["gesix"]
    assert any("GESIx" in s or "Senatsverwaltung" in s for s in _src_chk), _src_chk

    # Buergeramt tile sources use BOD attribution text (not key "buergeramt").
    _bur_src = _sources_for(_CFG_NL, "buergeramt", "green")
    assert _bur_src != ["buergeramt"], _bur_src
    assert any("ServicePortal" in s or "service.berlin.de" in s for s in _bur_src), _bur_src

    print("scorer.py: Newcomer lens (Task 4) selfchecks OK")
