"""Berlin curated data directories — hand-verified addresses, office
tuples, SESB bilingual-school registry, glossary regexes, and
OTHERS_ADMIN_CARDS registration.

Every entry here needs annual re-verification against its berlin.de
source — an out-of-date Standesamt address ships to production without
a data-quality signal. Keep that discipline: when re-verifying, cross
this file against the same landscape doc that guided the initial pull.
"""
import re

from app.cities.base import OthersAdminCardConfig

# Order matters: longer/multi-word forms first so "freier Träger" is matched
# before bare "Träger" (see phase3/server.py:GERMAN_GLOSS).
_BERLIN_GLOSSARY = [
    (re.compile(r"\bfreie[rnms]?\s+Träger\b"),           "a non-profit or private provider"),
    (re.compile(r"\bEigenbetrieb\b"),                     "city-run"),
    (re.compile(r"\bTräger\b"),                           "operator"),
    (re.compile(r"\bSituationsansatz\b"),                 "a child-led Berlin pedagogy"),
    (re.compile(r"\bSituationssatz\b"),                   "a child-led Berlin pedagogy"),  # common model misspelling
    (re.compile(r"\bGrundschule[n]?\b"),                  "primary school"),
    (re.compile(r"\bStaatliche Europa-Schule Berlin\b"),  "state bilingual school program"),
    (re.compile(r"\bSESB\b"),                             "state bilingual school program"),
    (re.compile(r"\bKita[s]?\b"),                         "daycare"),
]

_SESB_GRUNDSCHULEN = {
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

# --- Bureaucracy lens curated directories (Spec B) -------------------------
# Small, stable federal-adjacent directories. Hardcoded here per §14.4
# "BOD first, curated fallback" — the Berlin Geoportal doesn't cleanly
# publish these; curated is the honest choice for stable directories.
# ponytail: refresh annually or when a Bezirk merger/rename happens.

# One Standesamt per Bezirk (12 total). Names + addresses from berlin.de.
# Coordinates rounded to 4 decimals (~11 m precision). Verify at
# implementation time via Nominatim or Berlin's own address lookup.
_STANDESAMTS_BY_BEZIRK = {
    "Mitte":                          {"name": "Standesamt Mitte",
                                        "address": "Karl-Marx-Allee 31, 10178 Berlin",
                                        "lat": 52.5197, "lon": 13.4180},
    "Friedrichshain-Kreuzberg":       {"name": "Standesamt Friedrichshain-Kreuzberg",
                                        "address": "Schlesische Str. 27a, 10997 Berlin",
                                        "lat": 52.5008, "lon": 13.4460},
    "Pankow":                         {"name": "Standesamt Pankow",
                                        "address": "Fröbelstr. 17, 10405 Berlin",
                                        "lat": 52.5348, "lon": 13.4249},
    "Charlottenburg-Wilmersdorf":     {"name": "Standesamt Charlottenburg-Wilmersdorf",
                                        "address": "Otto-Suhr-Allee 100, 10585 Berlin",
                                        "lat": 52.5163, "lon": 13.3020},
    "Spandau":                        {"name": "Standesamt Spandau",
                                        "address": "Carl-Schurz-Str. 2/6, 13597 Berlin",
                                        "lat": 52.5350, "lon": 13.2010},
    "Steglitz-Zehlendorf":            {"name": "Standesamt Steglitz-Zehlendorf",
                                        "address": "Kirchstr. 1/3, 14163 Berlin",
                                        "lat": 52.4319, "lon": 13.2596},
    "Tempelhof-Schöneberg":           {"name": "Standesamt Tempelhof-Schöneberg",
                                        "address": "Rathausstr. 27, 12105 Berlin",
                                        "lat": 52.4685, "lon": 13.3888},
    "Neukölln":                       {"name": "Standesamt Neukölln",
                                        "address": "Karl-Marx-Str. 83, 12040 Berlin",
                                        "lat": 52.4813, "lon": 13.4400},
    "Treptow-Köpenick":               {"name": "Standesamt Treptow-Köpenick",
                                        "address": "Alt-Köpenick 21, 12555 Berlin",
                                        "lat": 52.4459, "lon": 13.5765},
    "Marzahn-Hellersdorf":            {"name": "Standesamt Marzahn-Hellersdorf",
                                        "address": "Riesaer Str. 94, 12627 Berlin",
                                        "lat": 52.5390, "lon": 13.6055},
    "Lichtenberg":                    {"name": "Standesamt Lichtenberg",
                                        "address": "Egon-Erwin-Kisch-Str. 106, 13059 Berlin",
                                        "lat": 52.5670, "lon": 13.5030},
    "Reinickendorf":                  {"name": "Standesamt Reinickendorf",
                                        "address": "Eichborndamm 215-239, 13437 Berlin",
                                        "lat": 52.5825, "lon": 13.3130},
}

# Finanzämter — ~17 offices across Berlin. Individual-income tax
# jurisdictions carve Berlin by street ranges, so this directory is a
# "starting point" (caveat on the lens tile carries this disclosure).
# ponytail: verify addresses at berlin.de/finanzaemter; annual refresh.
_FINANZAMTS = (
    {"name": "Finanzamt Charlottenburg",       "address": "Bismarckstr. 48, 10627 Berlin",
     "lat": 52.5075, "lon": 13.3060},
    {"name": "Finanzamt Friedrichshain-Kreuzberg", "address": "Möllendorffstr. 34, 10367 Berlin",
     "lat": 52.5225, "lon": 13.4550},
    {"name": "Finanzamt Lichtenberg",          "address": "Josef-Orlopp-Str. 62, 10365 Berlin",
     "lat": 52.5225, "lon": 13.4790},
    {"name": "Finanzamt Marzahn-Hellersdorf",  "address": "Allee der Kosmonauten 29, 10315 Berlin",
     "lat": 52.5305, "lon": 13.5265},
    {"name": "Finanzamt Mitte/Tiergarten",     "address": "Neue Jakobstr. 6-7, 10179 Berlin",
     "lat": 52.5140, "lon": 13.4160},
    {"name": "Finanzamt Neukölln",             "address": "Thiemannstr. 1, 12059 Berlin",
     "lat": 52.4680, "lon": 13.4530},
    {"name": "Finanzamt Pankow/Weißensee",     "address": "Storkower Str. 134, 10407 Berlin",
     "lat": 52.5290, "lon": 13.4560},
    {"name": "Finanzamt Prenzlauer Berg",      "address": "Storkower Str. 134, 10407 Berlin",
     "lat": 52.5290, "lon": 13.4560},
    {"name": "Finanzamt Reinickendorf",        "address": "Eichborndamm 208, 13437 Berlin",
     "lat": 52.5820, "lon": 13.3140},
    {"name": "Finanzamt Schöneberg",           "address": "Bundesallee 171, 10715 Berlin",
     "lat": 52.4820, "lon": 13.3335},
    {"name": "Finanzamt Spandau",              "address": "Nonnendammallee 15-21, 13599 Berlin",
     "lat": 52.5395, "lon": 13.2170},
    {"name": "Finanzamt Steglitz",             "address": "Schloßstr. 58-59, 12165 Berlin",
     "lat": 52.4570, "lon": 13.3260},
    {"name": "Finanzamt Tempelhof",            "address": "Tempelhofer Damm 234, 12099 Berlin",
     "lat": 52.4525, "lon": 13.3860},
    {"name": "Finanzamt Treptow-Köpenick",     "address": "Seelenbinderstr. 99, 12555 Berlin",
     "lat": 52.4570, "lon": 13.5770},
    {"name": "Finanzamt Wedding",              "address": "Osloer Str. 37, 13359 Berlin",
     "lat": 52.5540, "lon": 13.3800},
    {"name": "Finanzamt Wilmersdorf",          "address": "Volkslehrer- und Blissestr., 10713 Berlin",
     "lat": 52.4870, "lon": 13.3120},
    {"name": "Finanzamt Zehlendorf",           "address": "Martin-Buber-Str. 20, 14163 Berlin",
     "lat": 52.4330, "lon": 13.2540},
)

# Arbeitsagentur — Bundesagentur für Arbeit branches in Berlin.
# ~10 branches. Curated from arbeitsagentur.de.
_ARBEITSAGENTURS = (
    {"name": "Agentur für Arbeit Berlin Mitte",     "address": "Friedrichstr. 34, 10969 Berlin",
     "lat": 52.5063, "lon": 13.3900},
    {"name": "Agentur für Arbeit Berlin Nord",      "address": "Königin-Elisabeth-Str. 49, 14059 Berlin",
     "lat": 52.5290, "lon": 13.2880},
    {"name": "Agentur für Arbeit Berlin Süd",       "address": "Sonnenallee 282, 12057 Berlin",
     "lat": 52.4700, "lon": 13.4500},
    {"name": "Agentur für Arbeit Berlin Marzahn",   "address": "Allee der Kosmonauten 29, 12681 Berlin",
     "lat": 52.5410, "lon": 13.5910},
    {"name": "Agentur für Arbeit Berlin Neukölln",  "address": "Sonnenallee 282, 12057 Berlin",
     "lat": 52.4700, "lon": 13.4500},
    {"name": "Agentur für Arbeit Berlin Pankow",    "address": "Storkower Str. 118, 10407 Berlin",
     "lat": 52.5300, "lon": 13.4530},
    {"name": "Agentur für Arbeit Berlin Reinickendorf", "address": "Miraustr. 54, 13509 Berlin",
     "lat": 52.5900, "lon": 13.3320},
    {"name": "Agentur für Arbeit Berlin Spandau",   "address": "Altonaer Str. 70-72, 13581 Berlin",
     "lat": 52.5320, "lon": 13.2010},
    {"name": "Agentur für Arbeit Berlin Steglitz",  "address": "Kaiser-Wilhelm-Str. 1, 12247 Berlin",
     "lat": 52.4360, "lon": 13.3200},
    {"name": "Agentur für Arbeit Berlin Charlottenburg", "address": "Königin-Elisabeth-Str. 49, 14059 Berlin",
     "lat": 52.5290, "lon": 13.2880},
)

# LEA — Landesamt für Einwanderung, main office.
_LEA_OFFICE = {
    "name": "LEA Berlin — Landesamt für Einwanderung",
    "address": "Friedrich-Krause-Ufer 24, 13353 Berlin",
    "lat": 52.5450, "lon": 13.3616,
}

# --- Others tab: public-admin cards ---------------------------------------
# Was the Bureaucracy lens (Spec B). The traffic-light composer was removed
# once the underlying cards moved to the raw-view Others tab. Order matches
# the response tile order; icons key into the frontend `ico` map.
OTHERS_ADMIN_CARDS: tuple = (
    OthersAdminCardConfig(key="buergeramt",     label="Bürgeramt (Anmeldung)",           icon="buergeramt"),
    OthersAdminCardConfig(key="finanzamt",      label="Finanzamt (Tax Office)",          icon="finanzamt"),
    OthersAdminCardConfig(key="standesamt",     label="Standesamt (Marriage / Birth)",   icon="standesamt"),
    OthersAdminCardConfig(key="lea",            label="LEA (Residence Permit)",          icon="lea"),
    OthersAdminCardConfig(key="arbeitsagentur", label="Arbeitsagentur (Employment Agency)", icon="arbeitsagentur"),
)
