"""Hamburg curated data directories — hand-verified addresses, office
tuples, glossary regexes, and OTHERS_ADMIN_CARDS registration.

Every entry here has a "ponytail" comment on its parent `hamburg.py`
about annual re-verification against the hamburg.de source. Keep that
maintenance discipline: an out-of-date Standesamt address ships to
production without a data-quality signal.
"""
import re

from app.cities.base import OthersAdminCardConfig

# ---- 7 Bezirke: integer code → name (SozErhVo stores as int) ----------------
_BEZIRK_ID_TO_NAME = {
    1: "Hamburg-Mitte", 2: "Altona", 3: "Eimsbüttel",
    4: "Hamburg-Nord", 5: "Wandsbek", 6: "Bergedorf", 7: "Harburg",
}

# ---- Standesamt — 1 per Bezirk (7 entries from landscape doc §4.2). ---------
# Only admin office curated for Hamburg day-1 per spec Q10-B.
# ponytail: re-verify 2027-09 against hamburg.de/politik-und-verwaltung
# /bezirke/bezirksthemen/standesamt.
_STANDESAMTS_BY_BEZIRK = {
    "Hamburg-Mitte":  {"name": "Standesamt Hamburg-Mitte",
                        "address": "Caffamacherreihe 1–3, 20355 Hamburg",
                        "lat": 53.5544, "lon":  9.9845},
    "Altona":          {"name": "Standesamt Altona",
                        "address": "Platz der Republik 1, 22765 Hamburg",
                        "lat": 53.5470, "lon":  9.9357},
    "Eimsbüttel":      {"name": "Standesamt Eimsbüttel",
                        "address": "Grindelberg 62–66, 20144 Hamburg",
                        "lat": 53.5747, "lon":  9.9790},
    "Hamburg-Nord":    {"name": "Standesamt Hamburg-Nord",
                        "address": "Kümmellstraße 5–7, 20249 Hamburg",
                        "lat": 53.5899, "lon":  9.9845},
    "Wandsbek":        {"name": "Standesamt Wandsbek",
                        "address": "Schloßstraße 60, 22041 Hamburg",
                        "lat": 53.5717, "lon": 10.0708},
    "Bergedorf":       {"name": "Standesamt Bergedorf",
                        "address": "Gräpelweg 8, 21029 Hamburg (Haus im Park)",
                        "lat": 53.4891, "lon": 10.2190},
    "Harburg":         {"name": "Standesamt Harburg",
                        "address": "Harburger Rathausplatz 1, 21073 Hamburg",
                        "lat": 53.4591, "lon":  9.9795},
}

# ---- Regional rail curated list (13 from landscape §3.3) --------------------
_REGIONAL_RAIL = (
    ("Hamburg Hauptbahnhof",   53.55278, 10.00639),
    ("Hamburg-Altona",         53.55194,  9.93500),
    ("Hamburg Dammtor",        53.56083,  9.98944),
    ("Hamburg-Harburg",        53.45611,  9.99169),
    ("Hamburg-Bergedorf",      53.48944, 10.20639),
    ("Hamburg-Rahlstedt",      53.60333, 10.15806),
    ("Hamburg-Tonndorf",       53.59306, 10.13361),
    ("Wilhelmsburg",           53.4989,  10.0069),
    ("Pinneberg",              53.65917,  9.79139),
    ("Elbgaustraße",           53.6103,   9.9036),
    ("Neugraben",              53.4728,   9.8611),
    ("Aumühle",                53.5300,  10.3167),
    ("Buxtehude",              53.4747,   9.6931),
)

# ---- Hamburg-specific glossary (LLM post-processing) ------------------------
_HAMBURG_GLOSSARY = [
    (re.compile(r"\bKundenzentr\w*\b"),        "citizens' service office"),
    (re.compile(r"\bBezirk\b"),                "Hamburg borough"),
    (re.compile(r"\bStadtteil\b"),             "neighbourhood"),
    (re.compile(r"\bStatistisches Gebiet\b"),  "statistical area (~2200 residents)"),
    (re.compile(r"\bSozialmonitoring\b"),      "Hamburg's neighbourhood-status monitor"),
    (re.compile(r"\bAufmerksamkeitsgebiet\b"), "an area flagged for city social monitoring"),
    (re.compile(r"\bBücherhallen\b"),          "public library network"),
    (re.compile(r"\bHVV\b"),                   "Hamburg's transit union"),
    (re.compile(r"\bHADAG\b"),                 "Elbe ferry operator"),
    (re.compile(r"\bBewohnerparkgebiet\b"),    "resident parking zone"),
]

# ---- Kundenzentren (Hamburg's Bürgeramt equivalent) — 7 Bezirks-main -------
# Reuses the same buildings as _STANDESAMTS_BY_BEZIRK (each Bezirk hosts
# both under one roof at the same address). Stadtteil branches (~33 more)
# to be added post-launch when address geocoding is bulk-verified.
_KUNDENZENTREN = (
    {"name": "Kundenzentrum Hamburg-Mitte", "address": "Caffamacherreihe 1–3, 20355 Hamburg",  "lat": 53.5544, "lon":  9.9845},
    {"name": "Kundenzentrum Altona",         "address": "Platz der Republik 1, 22765 Hamburg",  "lat": 53.5470, "lon":  9.9357},
    {"name": "Kundenzentrum Eimsbüttel",     "address": "Grindelberg 62–66, 20144 Hamburg",     "lat": 53.5747, "lon":  9.9790},
    {"name": "Kundenzentrum Hamburg-Nord",   "address": "Kümmellstraße 5–7, 20249 Hamburg",     "lat": 53.5899, "lon":  9.9845},
    {"name": "Kundenzentrum Wandsbek",       "address": "Schloßstraße 60, 22041 Hamburg",       "lat": 53.5717, "lon": 10.0708},
    {"name": "Kundenzentrum Bergedorf",      "address": "Wentorfer Straße 38, 21029 Hamburg",   "lat": 53.4885, "lon": 10.2110},
    {"name": "Kundenzentrum Harburg",        "address": "Harburger Rathausplatz 1, 21073 Hamburg", "lat": 53.4591, "lon":  9.9795},
)

# ---- LEA equivalent — Hamburg's Einwohner-Zentralamt (Ausländerbehörde) ----
# One-office directory, same shape as Berlin's LEA. Verified 2026-09-21
# from hamburg.de/behoerdenfinder.
_LEA_OFFICE = {
    "name":    "Einwohner-Zentralamt (Ausländerangelegenheiten)",
    "address": "Amsinckstraße 28, 20097 Hamburg",
    "lat":     53.5468, "lon": 10.0135,
    "website": "https://www.hamburg.de/behoerdenfinder/hamburg/11331683/",
}

# ---- Arbeitsagentur Hamburg — 4 city branches per arbeitsagentur.de --------
_ARBEITSAGENTURS = (
    {"name": "Agentur für Arbeit Hamburg (Zentrale)",
     "address": "Kurt-Schumacher-Allee 16, 20097 Hamburg",
     "lat": 53.5497, "lon": 10.0136,
     "website": "https://www.arbeitsagentur.de/vor-ort/hamburg"},
    {"name": "Agentur für Arbeit Hamburg-Altona",
     "address": "Kieler Straße 39, 22769 Hamburg",
     "lat": 53.5786, "lon": 9.9391,
     "website": "https://www.arbeitsagentur.de/vor-ort/hamburg-altona"},
    {"name": "Agentur für Arbeit Hamburg-Harburg",
     "address": "Harburger Ring 35, 21073 Hamburg",
     "lat": 53.4602, "lon": 9.9855,
     "website": "https://www.arbeitsagentur.de/vor-ort/hamburg-harburg"},
    {"name": "Agentur für Arbeit Hamburg-Nord",
     "address": "Alsterdorfer Straße 262, 22297 Hamburg",
     "lat": 53.6142, "lon": 10.0136,
     "website": "https://www.arbeitsagentur.de/vor-ort/hamburg-nord"},
)

# ---- Curated intl / bilingual schools Hamburg (private + a few state) ------
# Hamburg's public schools WFS only ingests `staatliche_schulen`; most
# international schools are private and not in that layer. Curated list
# stands in until private-schools ingest lands. Shape matches Berlin's
# `bilingual_schools` intent but is a positional tuple so it can flow through
# `intl_schools_curated` → Index fallback in `nearest_intl`.
_INTL_SCHOOLS = (
    {"name":    "International School of Hamburg",
     "address": "Hemmingstedter Weg 130, 22609 Hamburg",
     "lat": 53.5719, "lon":  9.8434,
     "website": "https://www.ish.hamburg/",
     "kind":    "International (K–12)"},
    {"name":    "Phorms Hamburg (Bilingual)",
     "address": "Willi-Bredel-Straße 43, 22159 Hamburg",
     "lat": 53.6242, "lon": 10.1245,
     "website": "https://hamburg.phorms.de/",
     "kind":    "Bilingual DE/EN (K–12)"},
    {"name":    "Heinrich-Hertz-Schule (bilingual profile)",
     "address": "Grasweg 72–76, 22303 Hamburg",
     "lat": 53.5904, "lon":  9.9948,
     "website": "https://www.hhs-hamburg.de/",
     "kind":    "State bilingual DE/EN"},
    {"name":    "Katharineum zu Hamburg (Europa-Schule)",
     "address": "Bogenstraße 34–36, 20144 Hamburg",
     "lat": 53.5720, "lon":  9.9707,
     "website": "https://katharineum.hamburg/",
     "kind":    "Bilingual DE/EN"},
)

# ---- Finanzämter Hamburg — ~9 offices per Finanzbehörde directory ----------
_FINANZAMTS = (
    {"name": "Finanzamt Hamburg-Altona",      "address": "Große Bergstraße 264, 22767 Hamburg", "lat": 53.5497, "lon":  9.9345},
    {"name": "Finanzamt Hamburg-Am Tierpark", "address": "Am Tierpark 21, 22527 Hamburg",       "lat": 53.5928, "lon":  9.9425},
    {"name": "Finanzamt Hamburg-Barmbek-Uhlenhorst", "address": "Steilshooper Straße 129, 22305 Hamburg", "lat": 53.5949, "lon": 10.0454},
    {"name": "Finanzamt Hamburg-Bergedorf",   "address": "Neuer Weg 5, 21029 Hamburg",          "lat": 53.4870, "lon": 10.2100},
    {"name": "Finanzamt Hamburg-Hansa",       "address": "Steinstraße 10, 20095 Hamburg",       "lat": 53.5505, "lon": 10.0030},
    {"name": "Finanzamt Hamburg-Harburg",     "address": "Harburger Ring 10–14, 21073 Hamburg", "lat": 53.4619, "lon":  9.9870},
    {"name": "Finanzamt Hamburg-Mitte",       "address": "Rödingsmarkt 29, 20459 Hamburg",      "lat": 53.5486, "lon":  9.9847},
    {"name": "Finanzamt Hamburg-Nord",        "address": "Borsteler Chaussee 45, 22453 Hamburg", "lat": 53.6060, "lon":  9.9750},
    {"name": "Finanzamt Hamburg-Oberalster",  "address": "Am Ohlmoorgraben 4, 22391 Hamburg",   "lat": 53.6635, "lon": 10.0730},
)

# ---- Others admin cards: Kundenzentrum + Finanzamt + Standesamt + LEA + Arbeitsagentur ----
OTHERS_ADMIN_CARDS: tuple = (
    OthersAdminCardConfig(key="kundenzentrum",  label="Kundenzentrum (Anmeldung)",         icon="buergeramt"),
    OthersAdminCardConfig(key="finanzamt",      label="Finanzamt (Tax Office)",            icon="finanzamt"),
    OthersAdminCardConfig(key="standesamt",     label="Standesamt (Marriage / Birth)",     icon="standesamt"),
    OthersAdminCardConfig(key="lea",            label="LEA (Residence Permit)",            icon="lea"),
    OthersAdminCardConfig(key="arbeitsagentur", label="Arbeitsagentur (Employment Agency)", icon="arbeitsagentur"),
)
