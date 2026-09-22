"""Hamburg lens configs — Newcomer + Commuter tile lists.

Extracted from the flat `hamburg.py` into a dedicated module so lens
changes touch only the lens file. The audience-hint prose, per-tile
threshold dicts, and caveat strings live here verbatim from the flat
file; only imports changed.
"""
from app.cities.base import LensConfig, LensTileConfig


NEWCOMER_LENS: LensConfig = LensConfig(
    slug="newcomer",
    label="Newcomer",
    audience_hint="First 90 days in Hamburg — HVV, ferry, Anmeldung, English-friendly services.",
    tiles=(
        LensTileConfig(
            key="rail_transit", label="Rail Transit", icon="transit",
            thresholds={"sbahn_m": 800, "ubahn_m": 500, "any_rail_m": 1200},
        ),
        LensTileConfig(
            key="ferry_transit", label="Ferry Transit", icon="ferry",
            thresholds={"green_m": 500, "amber_m": 1000},
            caveat=("HVV-integrated HADAG ferry piers (route_type=4). All-day service on "
                    "lines 62, 64, 72; other lines are peak-only. Distance is walk to the "
                    "nearest pier, not to a specific line."),
        ),
        LensTileConfig(
            key="bus_transit", label="Bus Transit", icon="transit",
            thresholds={"green_m": 300, "amber_m": 600},
        ),
        LensTileConfig(
            key="intl_food", label="International food", icon="intl_food",
            thresholds={"radius_m": 1000, "green_count": 6, "amber_count": 2},
        ),
        LensTileConfig(
            key="coworking", label="Coworking + Wi-Fi cafés", icon="coworking",
            thresholds={"radius_m": 1000, "green_count": 3, "amber_count": 1},
        ),
        LensTileConfig(
            key="english_clinic", label="English-speaking clinic", icon="english_clinic",
            thresholds={"green_m": 1000, "amber_m": 3000},
            caveat="OSM community-tagged — inner-district coverage good, outer may under-report.",
        ),
        LensTileConfig(
            key="language_school", label="German classes", icon="language_school",
            thresholds={"green_m": 1500, "amber_m": 3500},
            caveat=("Covers Volkshochschule Hamburg + private Sprachschulen tagged in OSM; "
                    "small independent schools may be missing."),
        ),
        LensTileConfig(
            key="library", label="Public library", icon="library",
            thresholds={"green_m": 1000, "amber_m": 2500},
            caveat="Bücherhallen Hamburg branches from OSM operator tag.",
        ),
        LensTileConfig(
            key="packstation", label="Parcel pickup", icon="packstation",
            thresholds={"green_m": 400, "amber_m": 1000},
            caveat="DHL Packstation + Deutsche Post branches from OSM.",
        ),
        LensTileConfig(
            key="parkzone", label="Resident parking", icon="parkzone",
            thresholds={"amber_edge_m": 400},
            caveat=("Hamburg Bewohnerparkgebiete — LGV polygons. Green means inside a "
                    "zone (residents get a Bewohnerparkausweis) or ≥400 m from any zone "
                    "edge. Hourly fees + enforcement hours not published in the WFS."),
        ),
        LensTileConfig(
            key="nightlife_density", label="Nightlife density", icon="nightlife",
            thresholds={},
            caveat=("Numeric only — no green/amber/red verdict. Hamburg's Kiez density "
                    "(St. Pauli, Sternschanze) is a positive for some and a negative for "
                    "others; the noise tile covers the sound-level side of the same signal."),
        ),
        LensTileConfig(
            key="sozialmonitoring_status", label="Neighbourhood status", icon="gesix",
            thresholds={},
            caveat=("Hamburg BSW Sozialmonitoring — 4-level Statusindex per Statistisches "
                    "Gebiet (~2200 residents). 'Hoch' = strong socioeconomic status; "
                    "'sehr niedrig' = neighbourhood flagged for city support. Refreshed "
                    "annually; polygon grain is finer than Berlin's Planungsraum."),
        ),
        LensTileConfig(
            key="sozialmonitoring_gesamt", label="City-watch flag", icon="gesix",
            thresholds={},
            caveat=("Hamburg BSW Sozialmonitoring — combined Status+Dynamik verdict. "
                    "'Aufmerksamkeitsgebiet' = the polygon around this flat is a city-"
                    "designated area for social monitoring. Independent of the Status tile."),
        ),
    ),
)
COMMUTER_LENS: LensConfig = LensConfig(
    slug="commuter",
    label="Commuter",
    audience_hint="For someone who needs a fast, reliable daily commute in Hamburg.",
    tiles=(
        LensTileConfig(
            key="commuter_rail_transit", label="S+U-Bahn reach", icon="commuter_rail",
            thresholds={"sbahn_m": 500, "ubahn_m": 500, "any_rail_m": 900},
        ),
        LensTileConfig(
            key="commuter_ferry_transit", label="Ferry reach", icon="ferry",
            thresholds={"green_m": 400, "amber_m": 800},
            caveat=("HADAG piers (HVV route_type=4). Tighter than Newcomer threshold "
                    "because a daily 2× walk multiplies. All-day lines: 62, 64, 72."),
        ),
        LensTileConfig(
            key="commuter_bus_transit", label="Bus reach", icon="transit",
            thresholds={"green_m": 250, "amber_m": 500},
        ),
        LensTileConfig(
            key="regional_rail_reach", label="Regional rail reach", icon="regional_rail",
            thresholds={"green_m": 1200, "amber_m": 2500},
            caveat=("Curated list of Hamburg RE/RB + AKN stations. Doesn't cover every "
                    "S-Bahn stop the regional trains pass through; the tile is 'which "
                    "platform will your commuter train actually stop at'."),
        ),
        LensTileConfig(
            key="cycling_network", label="Cycling network reach", icon="bike_network",
            thresholds={"green_m": 100, "amber_m": 300},
            caveat=("OSM highway=cycleway from the weekly Geofabrik Hamburg extract. "
                    "Painted bike lanes on shared roads are NOT in this signal — only "
                    "dedicated infrastructure."),
        ),
        LensTileConfig(
            key="parkzone", label="Resident parking", icon="parkzone",
            thresholds={"amber_edge_m": 400},
            caveat=("Hamburg Bewohnerparkgebiete — for car-owning commuters: green "
                    "inside a zone (Bewohnerparkausweis priority) or well outside; "
                    "amber at the edge of a paid zone."),
        ),
        LensTileConfig(
            key="car_sharing_reach", label="Car-sharing reach", icon="car_sharing",
            thresholds={"radius_m": 500, "green_count": 3, "amber_count": 1},
            caveat=("Fixed pickup points from OSM community tags. Free-float zones "
                    "are NOT modelled — a station-based tile is the honest signal."),
        ),
        LensTileConfig(
            key="ev_charging_reach", label="EV charger reach", icon="bolt",
            thresholds={"radius_m": 500, "green_count": 2, "amber_count": 1},
        ),
        LensTileConfig(
            key="airport_reach", label="Airport reach (HAM)", icon="airport",
            thresholds={"green_km": 20, "amber_km": 35},
            caveat=("Straight-line distance to Hamburg Airport Helmut Schmidt. "
                    "Actual door-to-gate time depends on S1 / bus timing; this tile "
                    "is a rough exposure signal, not a routing."),
        ),
        LensTileConfig(
            key="sozialmonitoring_status_commuter", label="Neighbourhood status", icon="gesix",
            thresholds={},
            caveat=("Hamburg BSW Sozialmonitoring — same signal as Newcomer's status "
                    "tile, commuter-audience framing."),
        ),
        LensTileConfig(
            key="sozialmonitoring_gesamt_commuter", label="City-watch flag", icon="gesix",
            thresholds={},
            caveat="Hamburg BSW Sozialmonitoring — combined verdict.",
        ),
    ),
)
