#!/usr/bin/env python3
"""
Berlin Family Address Intelligence — Phase 2 (ship 1).

Phase 1 shipped catchment + schools + kita count + intl + OSM amenities.
Phase 2 ship 1 adds Berlin-Open-Data-first sourcing under a new rule:
where the city publishes a dataset, use it as primary and treat OSM as
supplement for known gaps.

Ship 1 diff from Phase 1:
  - Kitas now from Berlin Geoportal (kita WFS, ~2900 registered Kitas)
    with rich attrs (Träger, places, phone, web). OSM dropped for Kitas —
    the BOD layer is comprehensive and authoritative.
  - Playgrounds now from Berlin Geoportal (gruenanlagen:spielplaetze,
    polygons → centroids) with OSM leisure=playground as supplement for
    school/Kita/informal playgrounds excluded from the city dataset.
  - New category: parks / green space (gruenanlagen:gruenanlagen +
    OSM leisure=park supplement).

Run:  python3 server.py           # then open http://localhost:8000
Test: python3 server.py test
Deps: shapely  (pip3 install --user shapely)

Data:
  - Geoportal Berlin: schulen_esb, schulen, adressen_berlin, kita,
    gruenanlagen (spielplaetze + gruenanlagen layers)
                                              [dl-de/zero-2.0 / dl-de/by-2.0]
  - OSM Overpass: pharmacies, supermarkets, GPs, transit stops + playground
    and park supplements                                          [ODbL]

ponytail: proto-server. Production would move polygons into PostGIS with a
          nightly refresh, put a real framework in front, and rate-limit
          Overpass + WFS calls at the edge.
"""
import http.server, socketserver, json, urllib.request, urllib.parse
import threading, math, sys, os, unicodedata
from pathlib import Path
from shapely.geometry import shape, Point, mapping

HERE          = Path(__file__).parent
WFS_SCHULEN   = "https://gdi.berlin.de/services/wfs/schulen"
WFS_ADR       = "https://gdi.berlin.de/services/wfs/adressen_berlin"
WFS_KITA      = "https://gdi.berlin.de/services/wfs/kita"
WFS_GRUEN     = "https://gdi.berlin.de/services/wfs/gruenanlagen"
WFS_KKH       = "https://gdi.berlin.de/services/wfs/krankenhaeuser"
WFS_BRUNNEN   = "https://gdi.berlin.de/services/wfs/trinkwasserbrunnen"
WFS_NOISE     = "https://gdi.berlin.de/services/wfs/ua_stratlaerm_2022"
HOSPITAL_RADIUS_M = 2000   # hospitals aren't 800m-walk amenities; ~5 min drive covers all of Berlin
HOSPITAL_MATCH_M  = 500    # BOD entrance ↔ OSM way-center match tolerance (campuses can be large)
NOISE_LAYER   = "ua_stratlaerm_2022:aa_fp_gesamt2022"   # Fassadenpegel gesamt, 3.8M points
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
PORT          = int(os.environ.get("PORT", "8000"))

# --- Embedded LLM (Qwen2.5-0.5B-Instruct, 4-bit MLX) -----------------------
# Loaded in a background thread at startup so the HTTP server binds fast.
# ~300 MB weights cached in ~/.cache/huggingface after first pull.
# ponytail: single global model + serialising lock. If concurrent requests
# matter, run multiple workers — batching would be a much bigger rewrite.
LLM = {"model": None, "tokenizer": None, "error": None}
LLM_LOCK = threading.Lock()
LLM_MODEL_ID = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"

def _load_llm():
    try:
        from mlx_lm import load
        m, t = load(LLM_MODEL_ID)
        LLM["model"], LLM["tokenizer"] = m, t
        print(f"llm ready: {LLM_MODEL_ID}")
    except Exception as e:
        LLM["error"] = str(e)
        print(f"llm load failed: {e}", file=sys.stderr)

def summarize_impressions(address, votes):
    """One short generation per tab. votes = {tab: {'happy':[...], 'sad':[...]}}.
    Sentiment-aware: the prompt + few-shot are branched by mode (all-positive,
    all-negative, mixed) so a "the family disliked everything" input can't be
    twisted into "medical facilities are great" by a system prompt that assumed
    both a warm and an honest line would fit."""
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler, make_logits_processors
    sampler = make_sampler(temp=0.75, top_p=0.9)
    logits_procs = make_logits_processors(repetition_penalty=1.25)
    out = {}
    tok = LLM["tokenizer"]; mdl = LLM["model"]
    for tab, cats in (votes or {}).items():
        happy = cats.get("happy") or []
        sad   = cats.get("sad") or []
        if not happy and not sad: continue
        if happy and sad: mode = "mixed"
        elif happy:       mode = "positive"
        else:             mode = "negative"
        msgs = _build_impression_messages(mode, tab, address, happy, sad)
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        text = generate(mdl, tok, prompt=prompt, max_tokens=110,
                        sampler=sampler, logits_processors=logits_procs, verbose=False).strip()
        out[tab] = text
    return out


def _build_impression_messages(mode, tab, address, happy, sad):
    """Sentiment-matched system + few-shot. Small model can't reliably invent
    from nothing; every mode has an assistant example demonstrating the
    expected shape and tone for that exact sentiment."""
    liked    = ", ".join(happy)
    disliked = ", ".join(sad)
    if mode == "mixed":
        return [
            {"role": "system", "content":
                "You're a friendly Berliner giving a family your honest take on their new neighborhood, "
                "based on things they liked and things that bothered them nearby. "
                "Two short sentences, warm and specific. Speak to them as \"you\". No lists, no headings."},
            {"role": "user", "content":
                "Category: amenities. Address: Danziger Str. 44, 10405.\n"
                "Liked: Playgrounds, Parks.\n"
                "Bothered: Supermarkets.\n"},
            {"role": "assistant", "content":
                "You've landed on a proper family Kiez — the playgrounds and parks are why locals fight "
                "to stay here. The supermarket run is a bit of a slog though, so you'll want to plan the "
                "weekly shop around the S-Bahn instead of the corner."},
            {"role": "user", "content":
                f"Category: {tab}. Address: {address}.\nLiked: {liked}.\nBothered: {disliked}.\n"},
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
            "Do NOT claim things are good, do NOT invent positives. Write two honest sentences "
            "acknowledging the frustration and suggesting a practical workaround. Speak to them "
            "as \"you\". No lists, no headings."},
        {"role": "user", "content":
            "Category: medical. Address: Buschkrugallee 90, 12359.\n"
            "The family was unhappy with everything nearby: Pharmacies, Doctors, Hospitals.\n"},
        {"role": "assistant", "content":
            "You've spotted a real weak point of this Kiez — the medical options nearby are thin "
            "and none of them worked for you. Plan on registering with a Hausarzt closer to work "
            "instead, and keep the S-Bahn map handy for hospital runs when you need them."},
        {"role": "user", "content":
            f"Category: {tab}. Address: {address}.\n"
            f"The family was unhappy with everything nearby: {disliked}.\n"},
    ]

# Public SESB Grundschule strands (source: berlin.de/sen/bjf/schulen/besondere-schulen/sesb).
# WFS carries no SESB attribute, so a small hand-curated list is the only path.
# Substring match against schulname (lower-cased, ß-normalised).
SESB_GRUNDSCHULEN = {
    "aziz-nesin": "German-Turkish",
    "charles-dickens": "German-English",
    "christian-morgenstern": "German-Russian",
    "finow": "German-Italian",
    "homer": "German-Greek",
    "hunsruck": "German-Turkish",
    "joan-miro": "German-Spanish",
    "judith-kerr": "German-English",
    "kastanienbaum": "German-French",
    "konrad-duden": "German-Polish",
    "markische": "German-French",
    "neumark": "German-Portuguese",
    "regenbogen": "German-Portuguese",
    "wedding-grundschule": "German-French",
}
INTL_KEYWORDS = ("international", "english", "american", "british",
                 "bilingual", "bilinguale", "jfk", "kennedy", "europa")


# -- utilities ---------------------------------------------------------------

def norm(s: str) -> str:
    """Lower-case + strip diacritics (NFD, drop combining marks) + ß → ss."""
    s = s.lower().replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def wfs(base, **kw):
    kw.setdefault("service", "WFS")
    kw.setdefault("version", "2.0.0")
    kw.setdefault("request", "GetFeature")
    kw.setdefault("outputFormat", "application/json")
    kw.setdefault("srsName", "EPSG:4326")   # always WGS84 lon,lat
    url = base + "?" + urllib.parse.urlencode(kw)
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def cql_esc(s):
    return s.replace("'", "''")


def haversine_m(lon1, lat1, lon2, lat2):
    """Great-circle distance in metres."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def bbox_around(lon, lat, radius_m):
    """Small lat/lon bbox around a Berlin point. Rough, adequate for a WFS filter."""
    dlat = radius_m / 111_320
    dlon = radius_m / (111_320 * max(0.1, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


# -- BOD polygon features (per-request bbox WFS, cached) ---------------------

_bod_cache, _bod_lock = {}, threading.Lock()

def bod_polygon_features(base, type_name, lon, lat, radius_m=800):
    """Query a Berlin WFS polygon layer within a bbox. Returns list of
    {name, lat (centroid), lon (centroid), distance_m, area_m2, props, source}.

    ponytail: centroid + haversine, not nearest-boundary-point. Ceiling: for
    very large polygons (e.g., Tiergarten) the centroid can be 500m+ from the
    nearest edge; upgrade path is a projected CRS + shapely.distance."""
    key = (base, type_name, round(lon, 4), round(lat, 4), radius_m)
    with _bod_lock:
        if key in _bod_cache: return _bod_cache[key]
    minx, miny, maxx, maxy = bbox_around(lon, lat, radius_m)
    try:
        d = wfs(base, typeNames=type_name, count=200,
                bbox=f"{minx},{miny},{maxx},{maxy},EPSG:4326")
    except Exception as e:
        return [{"_error": str(e)}]
    out = []
    for f in d.get("features", []):
        g = f.get("geometry")
        if not g: continue
        try:
            geom = shape(g)
            c = geom.centroid
            cx, cy = c.x, c.y
        except Exception:
            continue
        dist = haversine_m(lon, lat, cx, cy)
        if dist > radius_m: continue        # centroid outside radius (bbox is looser)
        props = f.get("properties") or {}
        name = (props.get("namenr") or "").strip() or (props.get("planname") or "").strip() \
               or props.get("objartname") or "—"
        out.append({"name": name, "lat": cy, "lon": cx, "distance_m": round(dist),
                    "area_m2": props.get("katasterfl") or props.get("nettospfl"),
                    "props": props, "source": "bod"})
    out.sort(key=lambda x: x["distance_m"])
    with _bod_lock:
        _bod_cache[key] = out
    return out


# -- Façade-level noise (Berlin Strategische Lärmkarten 2022) ----------------

_noise_cache, _noise_lock = {}, threading.Lock()

def noise_at(lon, lat, search_radius_m=100):
    """Nearest façade point from the strategic noise map. Returns L_DEN / L_N
    per source (road, rail, aircraft, total in dB), distance to that point,
    and provenance — or {'unavailable': True} if no façade point exists
    within a reasonable radius (rare inside the S-Bahn ring, common on the
    outskirts). Bbox WFS query; expands once if the first bbox is empty.

    ponytail: nearest-point lookup, not spatial interpolation. Ceiling: for
    a Neubau where the nearest façade point is 40m across the block, we
    report that neighbour's number as a proxy — good enough for a street-
    quiet-vs-loud read; upgrade path is per-building geometry match."""
    key = (round(lon, 5), round(lat, 5))
    with _noise_lock:
        if key in _noise_cache: return _noise_cache[key]

    def _query(radius):
        minx, miny, maxx, maxy = bbox_around(lon, lat, radius)
        try:
            d = wfs(WFS_NOISE, typeNames=NOISE_LAYER, count=500,
                    bbox=f"{minx},{miny},{maxx},{maxy},EPSG:4326")
        except Exception as e:
            return None, str(e)
        return d.get("features", []), None

    feats, err = _query(search_radius_m)
    if err:
        return {"unavailable": True, "error": err[:200]}
    if not feats:
        feats, err = _query(search_radius_m * 3)  # ~300m fallback
        if err:
            return {"unavailable": True, "error": err[:200]}
    if not feats:
        return {"unavailable": True,
                "reason": "No façade measurement within 300 m (likely outside dense residential coverage)."}

    nearest, nearest_d = None, float("inf")
    for f in feats:
        g = f.get("geometry")
        if not g or g.get("type") != "Point": continue
        cx, cy = g["coordinates"]
        d = haversine_m(lon, lat, cx, cy)
        if d < nearest_d: nearest, nearest_d = f, d

    p = nearest["properties"]
    out = {
        "unavailable": False,
        "distance_m": round(nearest_d),
        "l_den": {                        # 24h day-evening-night weighted
            "total": p.get("ges_den"),
            "road":  p.get("str_den"),
            "rail":  p.get("sch_den"),
            "air":   p.get("flg_den"),
        },
        "l_night": {                      # 22:00–06:00
            "total": p.get("ges_n"),
            "road":  p.get("str_n"),
            "rail":  p.get("sch_n"),
            "air":   p.get("flg_n"),
        },
        "provenance": "Geoportal Berlin / Strategische Lärmkarten 2022 — Fassadenpegel gesamt (dl-de/by-2.0)",
    }
    with _noise_lock:
        _noise_cache[key] = out
    return out


def noise_tier(l_den_total):
    """WHO + EU-CNOSSOS action-plan thresholds → traffic-light tier for L_DEN (dB)."""
    if l_den_total is None: return "unknown"
    if l_den_total < 55:  return "green"      # WHO recommendation
    if l_den_total < 65:  return "amber"
    if l_den_total < 70:  return "orange"     # EU action-plan trigger
    return "red"


# -- Stroller score (pure rules; mirrored in JS for live UI updates) ---------

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


# -- data index (loaded once on startup) -------------------------------------

class Index:
    def __init__(self):
        sys.stdout.write("loading catchment polygons… "); sys.stdout.flush()
        esbs = wfs(WFS_SCHULEN, typeNames="schulen:schulen_esb", count=1000)
        self.esbs = [(f["properties"], shape(f["geometry"])) for f in esbs["features"]]
        print(f"{len(self.esbs)} polygons")

        sys.stdout.write("loading all schools… "); sys.stdout.flush()
        s = wfs(WFS_SCHULEN, typeNames="schulen:schulen", count=2000)
        self.schools = [(f["properties"], f["geometry"]["coordinates"])
                        for f in s["features"] if f.get("geometry")]

        self.gs_public = [(p, c) for p, c in self.schools
                          if p.get("schulart") == "Grundschule"
                          and p.get("traeger") == "öffentlich"]
        # School types that include primary years — Grundschule + combined + community.
        primary_types = {"Grundschule", "Gemeinschaftsschule", "Kombinierte allgemein bildende Schule"}
        self.gs_intl = [(p, c) for p, c in self.schools
                        if p.get("schulart") in primary_types
                        and any(k in norm(p["schulname"]) for k in INTL_KEYWORDS)]

        self.esb_to_gs = {}
        for props, geom in self.esbs:
            self.esb_to_gs[props["esb"]] = [
                (p, c) for p, c in self.gs_public if geom.contains(Point(c))
            ]
        print(f"{len(self.gs_public)} public Grundschulen · {len(self.gs_intl)} intl/bilingual")

        sys.stdout.write("loading kitas (Berlin geoportal)… "); sys.stdout.flush()
        k = wfs(WFS_KITA, typeNames="kita:kita", count=5000)
        self.kitas = [(f["properties"], f["geometry"]["coordinates"])
                      for f in k["features"] if f.get("geometry")]
        print(f"{len(self.kitas)} registered Kitas")

        sys.stdout.write("loading drinking fountains… "); sys.stdout.flush()
        # ~240 fountains city-wide; preload once, distance-filter per request.
        r = wfs(WFS_BRUNNEN, typeNames="trinkwasserbrunnen:trinkwasserbrunnen", count=1000)
        self.fountains = [(f["properties"], f["geometry"]["coordinates"])
                          for f in r.get("features", []) if f.get("geometry")]
        print(f"{len(self.fountains)} fountains")

        sys.stdout.write("loading hospitals (Berlin geoportal)… "); sys.stdout.flush()
        # Two layers: statutory "Plankrankenhäuser" (general hospitals incl. ERs)
        # and "weitere Krankenhäuser" (specialist clinics — eye, psych, …).
        # Both are points, both tiny (~110 total city-wide) — preload once.
        self.hospitals = []
        for layer, kind in (("plankrankenhaeuser", "plan"), ("weitere_krankenhaeuser", "weitere")):
            r = wfs(WFS_KKH, typeNames=f"krankenhaeuser:{layer}", count=500)
            for f in r.get("features", []):
                if not f.get("geometry"): continue
                p = dict(f["properties"]); p["_layer"] = kind
                self.hospitals.append((p, f["geometry"]["coordinates"]))
        print(f"{len(self.hospitals)} hospitals")

    def geocode(self, street, hnr, plz):
        r = wfs(WFS_ADR, typeNames="adressen_berlin:adressen_berlin",
                CQL_FILTER=f"str_name='{cql_esc(street)}' AND hnr='{cql_esc(hnr)}' AND plz='{cql_esc(plz)}'",
                count=1)
        if not r.get("features"):
            return None
        lon, lat = r["features"][0]["geometry"]["coordinates"]
        return {"lon": lon, "lat": lat, "props": r["features"][0]["properties"]}

    def catchment(self, lon, lat):
        pt = Point(lon, lat)
        for props, geom in self.esbs:
            if geom.contains(pt):
                return props, geom, self.esb_to_gs.get(props["esb"], [])
        return None, None, []

    def nearest_intl(self, lon, lat):
        if not self.gs_intl:
            return None
        best = min(self.gs_intl, key=lambda pc: haversine_m(lon, lat, pc[1][0], pc[1][1]))
        p, c = best
        return {"school": p, "lon": c[0], "lat": c[1],
                "distance_m": round(haversine_m(lon, lat, c[0], c[1]))}

    def sesb_strand(self, schulname):
        low = norm(schulname)
        for key, strand in SESB_GRUNDSCHULEN.items():
            if key in low:
                return strand
        return None

    def fountains_near_bod(self, lon, lat, radius_m=800):
        """Public drinking fountains within radius (BWB). Seasonal: most run
        May–October only; einschraenkungen flags out-of-service units."""
        hits = []
        for p, c in self.fountains:
            d = haversine_m(lon, lat, c[0], c[1])
            if d <= radius_m:
                loc = (p.get("standort") or "").strip() or "Trinkbrunnen"
                # Prepend "Trinkbrunnen" so list items scan the same as other categories.
                name = loc if loc.lower().startswith(("trinkbrunnen", "brunnen")) else f"Trinkbrunnen · {loc}"
                hits.append({
                    "name": name,
                    "lat": c[1], "lon": c[0], "distance_m": round(d),
                    "info": _fountain_info(p),
                    "props": p, "source": "bod",
                })
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def hospitals_near_bod(self, lon, lat, radius_m=HOSPITAL_RADIUS_M):
        """Hospitals within radius, from the two Krankenhäuser layers. Filters
        ~110 preloaded points by haversine — no per-request WFS."""
        hits = []
        for p, c in self.hospitals:
            d = haversine_m(lon, lat, c[0], c[1])
            if d <= radius_m:
                name = (p.get("kkh_standort") or p.get("name") or p.get("kkh") or "Krankenhaus").strip()
                hits.append({
                    "name": name,
                    "lat": c[1], "lon": c[0], "distance_m": round(d),
                    "info": _hospital_info(p),
                    "props": p, "source": "bod",
                })
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def kitas_near_bod(self, lon, lat, radius_m=800):
        """Registered Kitas within radius, from the Berlin geoportal.
        Returns list of {name, lat, lon, distance_m, info, props, source}.
        Filters ~2900 preloaded points by haversine — no per-request WFS call."""
        hits = []
        for p, c in self.kitas:
            d = haversine_m(lon, lat, c[0], c[1])
            if d <= radius_m:
                hits.append({
                    "name": (p.get("e_name") or "Kita").strip(),
                    "lat": c[1], "lon": c[0], "distance_m": round(d),
                    "info": _kita_info(p),
                    "props": p, "source": "bod",
                })
        hits.sort(key=lambda x: x["distance_m"])
        return hits


# -- OSM Overpass helper (falls back through public mirrors on failure) ------

def overpass(ql, timeout_s=60):
    """Try Overpass mirrors in order; return parsed JSON or raise last error."""
    err = None
    for url in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode({"data": ql}).encode(),
                headers={"User-Agent": "berlin-family-address-intel/0.1"})
            return json.loads(urllib.request.urlopen(req, timeout=timeout_s).read())
        except Exception as e:
            err = e
    raise err


# -- Kita summary formatter (used by Index.kitas_near_bod) -------------------

def _fountain_info(p):
    """One short line for a drinking fountain — flags out-of-service and season."""
    parts = []
    einschr = (p.get("einschraenkungen") or "").strip()
    if einschr:
        parts.append(f"⚠ {einschr}")
    if p.get("bezirk"): parts.append(p["bezirk"].strip())
    if p.get("trinkbrunnenart"):
        parts.append(f"Type: {p['trinkbrunnenart'].strip()}")
    # ponytail: season is buried in a free-text 'informationen' field;
    # a regex extract keeps it out of the summary and in the tooltip.
    return " · ".join(parts)


def _hospital_info(p):
    """One short line from a hospital feature's properties. 'Plan' hospitals
    show bed count + Träger; specialist 'weitere' clinics show speciality."""
    parts = []
    if p.get("_layer") == "weitere":
        fach = (p.get("fachabteilungen") or "").strip()
        if fach: parts.append(fach)
        if p.get("betten"): parts.append(f"{p['betten']} beds")
    else:
        beds = (p.get("betten_insgesamt") or "").strip()
        if beds: parts.append(f"{beds} beds")
        traeger = (p.get("kkh") or "").strip()
        if traeger and traeger != (p.get("kkh_standort") or "").strip():
            parts.append(traeger)
    if p.get("gc_ortsteil"): parts.append(p["gc_ortsteil"].strip())
    return " · ".join(parts)


def _kita_info(p):
    """One short line from a BOD Kita feature's properties."""
    parts = []
    if p.get("e_platz"):
        try:
            n = int(p["e_platz"]);  parts.append(f"{n} places")
        except (ValueError, TypeError): pass
    t_art = (p.get("t_art") or "").strip()
    if t_art:                       parts.append(t_art)      # e.g. "freie Träger", "Eigenbetrieb"
    ang = (p.get("ang_1") or "").strip()
    if ang and ang != "":           parts.append(ang)
    return " · ".join(parts)


# -- Kita lookup (BOD-first; OSM dropped — BOD is authoritative & richer) ----

def kitas_near(lon, lat, radius_m=800):
    """Return {'count', 'items', 'source', 'provenance'} — Berlin geoportal Kitas."""
    items = INDEX.kitas_near_bod(lon, lat, radius_m)
    return {"count": len(items), "items": items, "source": "bod",
            "provenance": "Geoportal Berlin / Kindertagesstätten (dl-de/by-2.0)"}


# -- OSM amenities (playgrounds, pharmacies, supermarkets, GPs, transit) -----

AMENITIES = [
    ("playgrounds",  '["leisure"="playground"]',                     "Playground"),
    ("parks",        '["leisure"="park"]',                           "Park"),
    ("pharmacies",   '["amenity"="pharmacy"]',                       "Pharmacy"),
    ("supermarkets", '["shop"="supermarket"]',                       "Supermarket"),
    ("gps",          '["amenity"="doctors"]',                        "Doctor's office"),
    ("transit",      '["public_transport"~"^(platform|station)$"]',  "Transit stop"),
]

# Which categories are supplemented by Berlin Open Data (BOD-first, OSM supplement).
# Others are OSM-only because the city doesn't publish them.
BOD_LAYERS = {
    "playgrounds": (WFS_GRUEN, "gruenanlagen:spielplaetze"),
    "parks":       (WFS_GRUEN, "gruenanlagen:gruenanlagen"),
}
BOD_DEDUPE_M = 50   # OSM item within this radius of a BOD centroid is a duplicate.

_amen_cache, _amen_lock = {}, threading.Lock()

def _classify_amenity(tags):
    if tags.get("leisure") == "playground":                        return "playgrounds"
    if tags.get("leisure") == "park":                              return "parks"
    if tags.get("amenity") == "pharmacy":                          return "pharmacies"
    if tags.get("shop") == "supermarket":                          return "supermarkets"
    if tags.get("amenity") == "doctors":                           return "gps"
    if tags.get("public_transport") in ("platform", "station"):    return "transit"
    return None

def _short_hours(oh):
    return oh if len(oh) <= 42 else oh[:39] + "…"

def _summarize(cat, tags):
    """One short human-readable line built from OSM tags. Empty = no useful data."""
    parts = []
    if cat == "transit":
        modes = []
        if tags.get("subway") == "yes" or tags.get("station") == "subway":   modes.append("U-Bahn")
        if tags.get("light_rail") == "yes" or tags.get("station") == "light_rail": modes.append("S-Bahn")
        if tags.get("tram") == "yes":  modes.append("Tram")
        if tags.get("bus") == "yes":   modes.append("Bus")
        if tags.get("train") == "yes": modes.append("Train")
        if modes: parts.append(" · ".join(modes))
        if tags.get("operator"):       parts.append(tags["operator"])
        if tags.get("wheelchair") == "yes": parts.append("Step-free")
    elif cat == "pharmacies":
        if tags.get("dispensing") == "yes":       parts.append("Prescriptions")
        if tags.get("opening_hours"):             parts.append(_short_hours(tags["opening_hours"]))
        if tags.get("phone"):                     parts.append("☎ " + tags["phone"])
        if tags.get("wheelchair") == "yes":       parts.append("Step-free")
    elif cat == "supermarkets":
        if tags.get("brand"):                     parts.append(tags["brand"])
        if tags.get("organic") == "yes":          parts.append("Organic")
        if tags.get("opening_hours"):             parts.append(_short_hours(tags["opening_hours"]))
    elif cat == "gps":
        spec = tags.get("healthcare:speciality") or tags.get("healthcare:specialty")
        if spec:                                  parts.append(spec.replace(";", ", ").replace("_", " ").title())
        if tags.get("phone"):                     parts.append("☎ " + tags["phone"])
        if tags.get("wheelchair") == "yes":       parts.append("Step-free")
    elif cat == "playgrounds":
        a_min = tags.get("min_age") or tags.get("age:min")
        a_max = tags.get("max_age") or tags.get("age:max")
        if a_min or a_max:                        parts.append(f"Ages {a_min or '?'}–{a_max or '?'}")
        if tags.get("surface"):                   parts.append("Surface: " + tags["surface"])
        if tags.get("fee") == "yes":              parts.append("Fee")
        if tags.get("wheelchair") == "yes":       parts.append("Step-free")
        if tags.get("fenced") == "yes":           parts.append("Fenced")
    elif cat == "parks":
        if tags.get("access") and tags["access"] != "yes":  parts.append(tags["access"].title())
        if tags.get("dog") == "leashed":         parts.append("Dogs on leash")
        if tags.get("wheelchair") == "yes":      parts.append("Step-free")
    return " · ".join(parts)


def _bod_area_summary(item):
    """One-liner summary for a BOD polygon feature (playground or park)."""
    parts = []
    a = item.get("area_m2")
    if a:
        try:
            a = float(a)
            parts.append(f"{a/10_000:.1f} ha" if a >= 10_000 else f"{int(a):,} m²")
        except (ValueError, TypeError): pass
    p = item.get("props") or {}
    if p.get("bezirkname"):                     parts.append(p["bezirkname"])
    if p.get("sanierjahr") and p["sanierjahr"].strip():
        parts.append(f"Renovated {p['sanierjahr'].strip()}")
    return " · ".join(parts)


def _merge_bod_and_osm(bod_items, osm_items, radius_m):
    """BOD-first, OSM as supplement. Drop OSM items within BOD_DEDUPE_M of any BOD centroid.
    Returns merged list, sorted by distance, with per-item 'source' preserved."""
    merged = []
    for it in bod_items:
        if it.get("_error"): continue
        merged.append({**it, "info": it.get("info") or _bod_area_summary(it)})
    for it in osm_items:
        if any(haversine_m(it["lon"], it["lat"], b["lon"], b["lat"]) < BOD_DEDUPE_M for b in merged):
            continue
        merged.append({**it, "source": "osm"})
    merged.sort(key=lambda x: x["distance_m"])
    return merged[:radius_m and 25]     # cap same as before

def amenities_near(lon, lat, radius_m=800):
    """One Overpass round-trip for all categories, then per-BOD-category WFS
    supplement for playgrounds and parks (BOD-first, OSM fills known gaps).

    ponytail: kept the combined Overpass query (per-category parallel was slower
    thanks to Overpass per-IP slot limits). BOD calls run sequentially after —
    each is a small bbox WFS and typically <300 ms."""
    key = (round(lon, 4), round(lat, 4), radius_m)
    with _amen_lock:
        if key in _amen_cache:
            return _amen_cache[key]

    # --- OSM round-trip -----------------------------------------------------
    # Extra hospital query at the wider hospital radius; not part of AMENITIES
    # because hospitals are BOD-first and OSM only supplies contact fields.
    hosp_ql = (f'nwr["amenity"="hospital"](around:{HOSPITAL_RADIUS_M},{lat},{lon});'
               f'nwr["healthcare"="hospital"](around:{HOSPITAL_RADIUS_M},{lat},{lon});')
    parts = hosp_ql + "".join(f"nwr{flt}(around:{radius_m},{lat},{lon});" for _, flt, _ in AMENITIES)
    ql = f"[out:json][timeout:60];({parts});out center tags;"
    try:
        d = overpass(ql, timeout_s=75)
        osm_ok = True
    except Exception as e:
        d = {"elements": []}
        osm_ok = False
        osm_err = str(e)

    fallback = {k: lbl for k, _, lbl in AMENITIES}
    buckets  = {k: [] for k, _, _ in AMENITIES}
    seen     = {k: set() for k, _, _ in AMENITIES}
    osm_hospitals = []                                  # for BOD-hospital enrichment below
    for el in d.get("elements", []):
        tags = el.get("tags") or {}
        lat_, lon_ = (el.get("lat"), el.get("lon")) if el["type"] == "node" \
                    else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        if lat_ is None: continue
        if tags.get("amenity") == "hospital" or tags.get("healthcare") == "hospital":
            osm_hospitals.append({"lat": lat_, "lon": lon_, "tags": tags})
            continue
        cat = _classify_amenity(tags)
        if not cat: continue
        name = tags.get("name") or fallback[cat]
        dkey = (name,) if cat == "transit" else (name, round(lat_, 5), round(lon_, 5))
        if dkey in seen[cat]: continue
        seen[cat].add(dkey)
        buckets[cat].append({"name": name, "lat": lat_, "lon": lon_,
                             "distance_m": round(haversine_m(lon, lat, lon_, lat_)),
                             "info": _summarize(cat, tags), "source": "osm",
                             "tags": tags})

    # --- BOD supplement (playgrounds, parks) --------------------------------
    result = {}
    for cat, _, _ in AMENITIES:
        osm_items = sorted(buckets[cat], key=lambda x: x["distance_m"])
        if cat in BOD_LAYERS:
            base, layer = BOD_LAYERS[cat]
            bod_items = bod_polygon_features(base, layer, lon, lat, radius_m)
            bod_err = next((b["_error"] for b in bod_items if b.get("_error")), None)
            bod_items = [b for b in bod_items if not b.get("_error")]
            merged = _merge_bod_and_osm(bod_items, osm_items, radius_m)
            n_bod, n_osm = sum(1 for x in merged if x["source"] == "bod"), sum(1 for x in merged if x["source"] == "osm")
            prov = _mixed_provenance(cat, n_bod, n_osm, bod_err)
            result[cat] = {"count": len(merged), "items": merged[:25],
                           "bod_count": n_bod, "osm_count": n_osm, "provenance": prov}
        else:
            result[cat] = {"count": len(osm_items), "items": osm_items[:25],
                           "provenance": "© OpenStreetMap contributors (ODbL)"}
    if not osm_ok:
        # OSM completely failed — still return BOD-backed categories; mark OSM-only ones as errored.
        for cat, _, _ in AMENITIES:
            if cat not in BOD_LAYERS:
                result[cat] = {"count": None, "items": [], "error": osm_err}

    # Hospitals: BOD-first for identity (name, beds, Träger) with OSM overlay
    # for contact fields the city doesn't publish (emergency, phone, website,
    # wheelchair). Match by nearest OSM within HOSPITAL_MATCH_M — campuses in
    # OSM are usually ways, so their `center` may sit up to a few hundred metres
    # from the BOD entrance point.
    hosp = INDEX.hospitals_near_bod(lon, lat, HOSPITAL_RADIUS_M)
    n_enriched = 0
    if osm_hospitals:
        for h in hosp:
            match, best = None, HOSPITAL_MATCH_M
            for o in osm_hospitals:
                d = haversine_m(h["lon"], h["lat"], o["lon"], o["lat"])
                if d <= best: match, best = o, d
            if match:
                t = match["tags"]
                h["osm"] = {
                    "emergency":  t.get("emergency"),
                    "phone":      t.get("phone") or t.get("contact:phone"),
                    "website":    t.get("website") or t.get("contact:website"),
                    "wheelchair": t.get("wheelchair"),
                    "match_m":    round(best),
                }
                n_enriched += 1
    prov = "Geoportal Berlin / Krankenhäuser (dl-de/by-2.0)"
    if n_enriched:
        prov += f" + © OpenStreetMap contributors (ODbL) — contact/ER for {n_enriched}/{len(hosp)}"
    elif not osm_ok:
        prov += f" · OSM overlay unavailable"
    result["hospitals"] = {
        "count": len(hosp), "items": hosp[:25],
        "radius_m": HOSPITAL_RADIUS_M, "osm_enriched": n_enriched,
        "provenance": prov,
    }

    # Public drinking fountains (BWB): BOD-only, walkable stroller amenity.
    fountains = INDEX.fountains_near_bod(lon, lat, radius_m)
    result["fountains"] = {
        "count": len(fountains), "items": fountains[:25],
        "provenance": "Geoportal Berlin / Trinkwasserbrunnen (dl-de/by-2.0) · Betrieb: Berliner Wasserbetriebe",
    }

    with _amen_lock:
        _amen_cache[key] = result
    return result


def _mixed_provenance(cat, n_bod, n_osm, bod_err):
    """Human-readable provenance string reflecting what actually contributed."""
    bod_name = "Geoportal Berlin / Grünanlagen — " + (
        "Spielplätze" if cat == "playgrounds" else "Grünanlagen")
    osm_name = "© OpenStreetMap contributors (ODbL)"
    if bod_err:
        return f"{osm_name} · BOD unavailable ({bod_err[:60]})"
    if n_bod and n_osm:  return f"{bod_name} (dl-de/by-2.0) + {osm_name} supplement"
    if n_bod:            return f"{bod_name} (dl-de/by-2.0)"
    return osm_name


# -- HTTP handler ------------------------------------------------------------

INDEX = None  # populated in main()

def parse_address(q: str):
    """Very loose 'Street 12, 10435' parser. Returns (street, hnr, plz) or None."""
    q = (q or "").strip()
    if not q:
        return None
    if "," in q:
        left, right = q.rsplit(",", 1)
        plz = "".join(ch for ch in right if ch.isdigit())[:5]
    else:
        parts = q.split()
        if len(parts) < 2: return None
        plz = parts[-1] if parts[-1].isdigit() and len(parts[-1]) == 5 else ""
        left = " ".join(parts[:-1]) if plz else q
    tokens = left.strip().split()
    hnr = ""
    for i in range(len(tokens) - 1, -1, -1):
        if any(ch.isdigit() for ch in tokens[i]):
            hnr = tokens[i]; street = " ".join(tokens[:i]); break
    else:
        return None
    if not street or not plz:
        return None
    return street, hnr, plz


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, ctype):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            return self._file(HERE / "index.html", "text/html; charset=utf-8")
        if u.path == "/health":
            return self._json({"ok": True, "polygons": len(INDEX.esbs),
                               "llm_ready": LLM["model"] is not None, "llm_error": LLM["error"]})
        if u.path == "/api/lookup":
            return self._lookup(qs)
        if u.path == "/api/amenities":
            return self._amenities(qs)
        if u.path == "/api/noise":
            return self._noise(qs)
        self.send_error(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/impression":
            return self._impression()
        self.send_error(404)

    def _impression(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode("utf-8") if n else "{}"
            d = json.loads(body)
        except Exception as e:
            return self._json({"error": f"bad body: {e}"}, 400)
        if LLM["model"] is None:
            return self._json({"error": LLM["error"] or "AI model still warming up, try again in a moment."}, 503)
        addr = (d.get("address") or "this address").strip()[:120]
        votes = d.get("votes") or {}
        try:
            with LLM_LOCK:                    # llama/mlx not thread-safe
                summary = summarize_impressions(addr, votes)
        except Exception as e:
            return self._json({"error": f"generation failed: {e}"}, 500)
        return self._json({"summary": summary, "model": LLM_MODEL_ID})

    def _noise(self, qs):
        try:
            lat = float((qs.get("lat") or [""])[0])
            lon = float((qs.get("lon") or [""])[0])
        except ValueError:
            return self._json({"error": "lat and lon required"}, 400)
        n = noise_at(lon, lat)
        n["tier"] = noise_tier((n.get("l_den") or {}).get("total")) if not n.get("unavailable") else "unknown"
        return self._json({"noise": n})

    def _amenities(self, qs):
        try:
            lat = float((qs.get("lat") or [""])[0])
            lon = float((qs.get("lon") or [""])[0])
        except ValueError:
            return self._json({"error": "lat and lon required"}, 400)
        return self._json({
            "amenities": amenities_near(lon, lat, 800),
            "provenance": "Berlin Open Data + OpenStreetMap (see per-category source)",
        })

    def _lookup(self, qs):
        addr = (qs.get("address") or [""])[0].strip()
        street = (qs.get("street") or [""])[0].strip()
        hnr    = (qs.get("hnr")    or [""])[0].strip()
        plz    = (qs.get("plz")    or [""])[0].strip()

        if addr and not (street and hnr and plz):
            p = parse_address(addr)
            if not p:
                return self._json({"error": "Could not parse address. Try 'Kastanienallee 12, 10435'."}, 400)
            street, hnr, plz = p

        if not (street and hnr and plz):
            return self._json({"error": "Missing street/hnr/plz."}, 400)

        try:
            geo = INDEX.geocode(street, hnr, plz)
        except Exception as e:
            return self._json({"error": f"Geocoder unavailable: {e}"}, 502)
        if not geo:
            return self._json({"error": f"No Berlin address matched '{street} {hnr}, {plz}'."}, 404)

        lon, lat = geo["lon"], geo["lat"]
        esb_props, polygon, schools = INDEX.catchment(lon, lat)

        out_schools = []
        for s, c in schools:
            out_schools.append({
                "name": s["schulname"], "bsn": s["bsn"],
                "street": s.get("strasse", "").strip(),
                "hnr": s.get("hausnr", "").strip(),
                "plz": s.get("plz", ""),
                "phone": s.get("telefon"), "website": s.get("internet"),
                "sesb_strand": INDEX.sesb_strand(s["schulname"]),
                "school_year": s.get("schuljahr"),
                "lon": c[0], "lat": c[1],
            })

        intl = INDEX.nearest_intl(lon, lat)
        intl_out = None
        if intl:
            s = intl["school"]
            intl_out = {"name": s["schulname"], "bsn": s["bsn"],
                        "distance_m": intl["distance_m"],
                        "lat": intl["lat"], "lon": intl["lon"],
                        "website": s.get("internet")}

        kitas = kitas_near(lon, lat, 800)

        return self._json({
            "address": {"street": street, "hnr": hnr, "plz": plz,
                        "lon": lon, "lat": lat, "raw": geo["props"]},
            "catchment": {
                "esb": esb_props["esb"] if esb_props else None,
                "district": esb_props["bezname"] if esb_props else None,
                "polygon": mapping(polygon) if polygon is not None else None,
            },
            "schools": out_schools,
            "intl_grundschule": intl_out,
            "kitas": kitas,
            "provenance": {
                "catchment":  "Geoportal Berlin / Schulen (dl-de/zero-2.0)",
                "schools":    "Geoportal Berlin / Schulen (dl-de/zero-2.0)",
                "addresses":  "Geoportal Berlin / Adressen Berlin (dl-de/by-2.0)",
                "kitas":      "Geoportal Berlin / Kindertagesstätten (dl-de/by-2.0)",
            },
        })


# -- self-check (ponytail: one runnable check that fails if logic breaks) ----

def _selfcheck():
    global INDEX
    INDEX = Index()
    idx = INDEX
    geo = idx.geocode("Kastanienallee", "12", "10435")
    assert geo, "known Prenzlauer Berg address must geocode"
    props, poly, schools = idx.catchment(geo["lon"], geo["lat"])
    assert props and props["bezname"] == "Pankow"
    assert any("Senefelderplatz" in s["schulname"] for s, _ in schools)
    assert all(isinstance(c, list) and len(c) == 2 for _, c in schools), "schools carry [lon,lat]"
    intl = idx.nearest_intl(geo["lon"], geo["lat"])
    assert intl and intl["distance_m"] < 10_000
    assert idx.sesb_strand("Joan-Miró-Grundschule") == "German-Spanish"
    assert _classify_amenity({"amenity": "pharmacy"}) == "pharmacies"
    assert _classify_amenity({"leisure": "park"}) == "parks", "leisure=park must classify as parks"
    assert _classify_amenity({"public_transport": "platform"}) == "transit"
    assert _classify_amenity({"amenity": "restaurant"}) is None
    assert _summarize("transit", {"subway": "yes", "tram": "yes", "operator": "BVG"}) == "U-Bahn · Tram · BVG"
    assert _summarize("playgrounds", {"min_age": "3", "max_age": "12", "surface": "sand"}) == "Ages 3–12 · Surface: sand"
    assert _summarize("supermarkets", {}) == ""
    assert _summarize("parks", {"dog": "leashed", "wheelchair": "yes"}) == "Dogs on leash · Step-free"

    # BOD Kita coverage — Berlin should have ≥ 2500 registered Kitas city-wide.
    assert len(idx.kitas) >= 2500, f"expected ≥2500 BOD Kitas, got {len(idx.kitas)}"
    # Kastanienallee 12 is dense Prenzlauer Berg — expect several Kitas within 800m.
    ks = idx.kitas_near_bod(geo["lon"], geo["lat"], 800)
    assert len(ks) >= 3, f"expected ≥3 BOD Kitas near Kastanienallee 12, got {len(ks)}"
    assert all(k["source"] == "bod" and k["distance_m"] <= 800 for k in ks)

    # Kita info formatter — synthetic props (avoids network dependency in this assert).
    assert "65 places" in _kita_info({"e_platz": "65", "t_art": "freie Träger", "ang_1": ""})

    # Hospitals — Berlin should have ~110 total (64 plan + 47 weitere as of 2026).
    assert len(idx.hospitals) >= 80, f"expected ≥80 hospitals city-wide, got {len(idx.hospitals)}"
    hs = idx.hospitals_near_bod(geo["lon"], geo["lat"], 2000)
    assert len(hs) >= 1, f"expected ≥1 hospital within 2km of Kastanienallee 12, got {len(hs)}"
    assert all(h["source"] == "bod" and h["distance_m"] <= 2000 for h in hs)
    # Widen radius: Charité / St. Hedwig / Vivantes should be within 5km of Prenzlauer Berg.
    hs_wide = idx.hospitals_near_bod(geo["lon"], geo["lat"], 5000)
    assert len(hs_wide) >= 5, f"expected ≥5 hospitals within 5km, got {len(hs_wide)}"
    assert any("Hedwig" in h["name"] or "Charité" in h["name"] for h in hs_wide), \
        "Charité or St. Hedwig should be within 5km of Prenzlauer Berg"
    # Hospital info formatter — beds + Ortsteil.
    plan = _hospital_info({"_layer": "plan", "betten_insgesamt": "415",
                           "kkh": "Alexianer", "kkh_standort": "St. Hedwig",
                           "gc_ortsteil": "Mitte"})
    assert "415 beds" in plan and "Mitte" in plan and "Alexianer" in plan
    weit = _hospital_info({"_layer": "weitere", "fachabteilungen": "Augenheilkunde",
                           "betten": 4, "gc_ortsteil": "Schöneberg"})
    assert "Augenheilkunde" in weit and "4 beds" in weit

    # OSM hospital match-radius sanity: within-500m match wins, farther is dropped.
    _bod = {"lat": 52.500, "lon": 13.400}
    _near = {"lat": 52.5025, "lon": 13.4025, "tags": {"emergency": "yes", "phone": "+49 30 1"}}   # ~330 m
    _far  = {"lat": 52.510,  "lon": 13.410,  "tags": {"emergency": "no",  "phone": "+49 30 2"}}   # ~1300 m
    assert haversine_m(_bod["lon"], _bod["lat"], _near["lon"], _near["lat"]) < HOSPITAL_MATCH_M
    assert haversine_m(_bod["lon"], _bod["lat"], _far["lon"],  _far["lat"])  > HOSPITAL_MATCH_M

    # Drinking fountains — Berlin has ~240 BWB fountains city-wide.
    assert len(idx.fountains) >= 150, f"expected ≥150 fountains, got {len(idx.fountains)}"
    # Kastanienallee 12 sits near several — Volkspark am Weinbergsweg is close.
    fs = idx.fountains_near_bod(geo["lon"], geo["lat"], 800)
    assert all(f["source"] == "bod" and f["distance_m"] <= 800 for f in fs)
    fs_wide = idx.fountains_near_bod(geo["lon"], geo["lat"], 3000)
    assert len(fs_wide) >= 3, f"expected ≥3 fountains within 3km of Kastanienallee 12, got {len(fs_wide)}"
    # Formatter — out-of-service flag surfaces first.
    off = _fountain_info({"einschraenkungen": "zur Zeit wegen Reparatur außer Betrieb",
                          "bezirk": "Neukölln", "trinkbrunnenart": "Kaiser"})
    assert off.startswith("⚠ ") and "Neukölln" in off and "Kaiser" in off
    ok = _fountain_info({"einschraenkungen": None, "bezirk": "Mitte", "trinkbrunnenart": "Kaiser"})
    assert not ok.startswith("⚠") and "Mitte" in ok

    # BOD polygon fetch — parks near the same address.
    parks = bod_polygon_features(WFS_GRUEN, "gruenanlagen:gruenanlagen", geo["lon"], geo["lat"], 800)
    parks = [p for p in parks if not p.get("_error")]
    assert len(parks) >= 1, "expected ≥1 BOD park within 800m of Kastanienallee 12"
    assert all(p["source"] == "bod" and 0 < p["distance_m"] <= 800 for p in parks)

    # BOD/OSM merge dedupe — OSM item colocated with a BOD item is dropped.
    bod = [{"name": "A", "lat": 52.5, "lon": 13.4, "distance_m": 100, "source": "bod", "area_m2": 1000, "props": {}}]
    osm_dup  = [{"name": "A", "lat": 52.5, "lon": 13.4, "distance_m": 100, "info": ""}]  # same spot
    osm_new  = [{"name": "B", "lat": 52.6, "lon": 13.5, "distance_m": 200, "info": ""}]  # far away
    merged   = _merge_bod_and_osm(bod, osm_dup + osm_new, 800)
    assert len(merged) == 2 and {m["source"] for m in merged} == {"bod", "osm"}

    # Noise thresholds — pure function.
    assert noise_tier(50)   == "green"
    assert noise_tier(60)   == "amber"
    assert noise_tier(68)   == "orange"
    assert noise_tier(75)   == "red"
    assert noise_tier(None) == "unknown"

    # Stroller scoring — rule-based, must stay in sync with the JS mirror.
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

    # Noise lookup — Kurfürstendamm 195 sits on a Berlin B-road with tram; L_DEN
    # should clearly exceed the WHO 55 dB threshold. If BOD is unreachable, skip.
    kurf = idx.geocode("Kurfürstendamm", "195", "10707")
    assert kurf, "Kurfürstendamm 195 must geocode"
    n = noise_at(kurf["lon"], kurf["lat"])
    if n.get("unavailable"):
        print(f"selfcheck: noise WFS unavailable ({n.get('error') or n.get('reason')}) — skipped assertion")
    else:
        assert n["l_den"]["total"] and n["l_den"]["total"] > 55, \
            f"expected L_DEN > 55 on Kurfürstendamm 195, got {n['l_den']}"
        assert n["distance_m"] < 60, f"nearest façade point should be close; got {n['distance_m']} m"
    print("selfcheck: OK")


def main():
    global INDEX
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        return _selfcheck()
    INDEX = Index()
    # Load LLM in background so the HTTP server binds without waiting.
    threading.Thread(target=_load_llm, daemon=True, name="llm-loader").start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True  # ponytail: instant restart, no TIME_WAIT wait
    with socketserver.ThreadingTCPServer(("", PORT), H) as srv:
        print(f"→ http://localhost:{PORT}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")


if __name__ == "__main__":
    main()
