"""Hamburg lens configs — Newcomer + Commuter + Quiet Living tile lists.

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
            caveat=("Hamburg city rating of the ~2,200-resident block on income, jobs, "
                    "education, and family stability. Refreshed yearly. Reflects the block, "
                    "not the building."),
        ),
        LensTileConfig(
            key="sozialmonitoring_gesamt", label="City focus area", icon="gesix",
            thresholds={},
            caveat=("Tags blocks the city has picked for extra social support — either weak "
                    "now, or trending down. Independent of the Neighbourhood status tile."),
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
            caveat=("Same signal as Newcomer's Neighbourhood status tile — commuter-audience "
                    "framing."),
        ),
        LensTileConfig(
            key="sozialmonitoring_gesamt_commuter", label="City focus area", icon="gesix",
            thresholds={},
            caveat="Same signal as Newcomer's City focus area tile — commuter-audience framing.",
        ),
    ),
)

# --- Quiet Living lens ------------------------------------------------------
# Eight tiles for someone who wants a calm, low-noise home in Hamburg. Shape
# mirrors Berlin's QUIET_LIVING_LENS with per-city adjustments:
#   - `street_trees` uses a tree-COUNT density fallback because Hamburg's
#     `strassenbaumkataster` layer carries no `kronedurch` field, so the
#     crown-coverage-% path always reads 0. Green anchor 60 / amber 20
#     inside the loader's 200 m disk; see `_tier_street_trees_density`.
#   - `heat` (Stadtklimaanalyse 2023) replaces Berlin's `air` slot —
#     Hamburg publishes no per-street NO₂ (spec Q10). Same PET-Belastung
#     class shape as the Berlin YF heat tile, reuses `_tier_heat`.
#   - `sozialmonitoring_status_quiet` replaces `gesix_quiet` — Hamburg has
#     no GESIx dataset; shape-only tile mirrors Berlin's gesix_quiet
#     pattern using the BSW Sozialmonitoring statusindex signal.
# Berlin QL's `rail_noise` tile is intentionally omitted for Hamburg: the
# Berlin implementation treats U-Bahn as "always green" because Berlin's
# U-Bahn is largely underground, but HH's U-Bahn (U1 / U3) has long
# elevated stretches — the shortcut inverts on HH addresses. Rewiring is
# a follow-up.
# Berlin QL's `noise` tile is also omitted: Hamburg publishes Strategische
# Lärmkarten only as WMS raster + shapefile ZIP download, no WFS. The
# `noise_bands_at` code path + `_tier_noise_isoline` helper remain wired
# for a future ingest, but no runtime data source exists so the tile was
# removed from the lens config until a shapefile ingest lands.
QUIET_LIVING_LENS: LensConfig = LensConfig(
    slug="quiet_living",
    label="Quiet Living",
    audience_hint="For someone who wants a calm, low-noise home in Hamburg",
    tiles=(
        LensTileConfig(
            key="quiet_zone", label="Nearest quiet zone", icon="refuge",
            thresholds={"green_m": 400, "amber_m": 1000},
            caveat=("Hamburg's Ruhige Gebiete + Ruheinseln (§47d BImSchG) — "
                    "polygons combining acoustic quiet with recreation value. "
                    "Distance is to the polygon edge."),
        ),
        LensTileConfig(
            key="street_trees", label="Street tree density", icon="refuge",
            # Count-based fallback — Hamburg's Straßenbaumkataster carries
            # no crown-diameter field, so the Berlin crown-coverage % path
            # would always read 0%. Green ≥ 60 trees inside a 200 m disk
            # (mature two-sided tree lining); amber ≥ 20 (some canopy);
            # red < 20 (sparse / no street trees).
            thresholds={"green_count": 60, "amber_count": 20},
            caveat=("Count of registered street trees inside a 200 m radius "
                    "disk (Hamburg Straßenbaumkataster, BUKEA). No canopy-% "
                    "reading because the source layer lacks a crown-diameter "
                    "field — this tile is a density proxy, not a shade "
                    "measurement. Only registered street trees; park and "
                    "private-garden trees are not included."),
        ),
        LensTileConfig(
            key="tempo30", label="Speed limit at your street", icon="tempo30",
            thresholds={"green_kmh": 30, "amber_kmh": 50, "default_kmh": 50},
            caveat=("Hamburg's `zulaessige_hoechstgeschwindigkeiten` WFS "
                    "lists exceptions to the general 50 km/h. Absence of a "
                    "nearby exception is reported as 'default 50 km/h', "
                    "not unknown."),
        ),
        LensTileConfig(
            key="arterial_road", label="Distance to arterial road", icon="arterial_road",
            thresholds={"green_m": 150, "amber_m": 50},
            caveat=("Straßen- und Wegenetz (BVM via LGV) — Hamburg's road "
                    "network with class attribution. Distance to the nearest "
                    "arterial-class segment is a rough proxy for exposure "
                    "to traffic noise and dust."),
        ),
        LensTileConfig(
            key="cobblestone_nearby", label="Cobblestone nearby", icon="cobblestone",
            thresholds={"green_m": 100, "amber_m": 30},
            caveat=("OSM `highway=residential|unclassified|tertiary|"
                    "secondary|primary|living_street` AND `surface="
                    "sett|cobblestone|unhewn_cobblestone` on trafficked "
                    "roads only — cobble sidewalks and paving_stones are "
                    "excluded. Hamburg extract from the weekly Geofabrik "
                    "snapshot; way centroid is the query anchor."),
        ),
        LensTileConfig(
            key="nightlife_inverted", label="Nightlife within 300 m", icon="nightlife",
            thresholds={"radius_m": 300, "green_max": 3, "amber_max": 8},
            caveat=("Inverse of the Newcomer nightlife tile — fewer bars/"
                    "clubs/pubs within 300 m is greener here. Same OSM "
                    "data (Hamburg Geofabrik extract), opposite framing."),
        ),
        LensTileConfig(
            key="heat", label="Summer heat", icon="heat",
            # Same PET-Belastung class strings as Berlin's YF heat tile —
            # matched case-insensitively as substrings against Hamburg's
            # `bewertung_tag` field (values like "Sehr starke Belastung
            # (38 °C bis <= 41 °C)"). Hot addresses = windows shut in
            # summer = louder outdoor noise leaks in.
            thresholds={
                "green_classes": ("keine Belastung", "geringe Belastung"),
                "amber_classes": ("mäßige Belastung", "starke Belastung"),
            },
            caveat=("Stadtklimaanalyse 2023 (BUKEA) — PET (Physiological "
                    "Equivalent Temperature) day-class per residential block. "
                    "Reflects the block, not the specific building."),
        ),
        LensTileConfig(
            key="sozialmonitoring_status_quiet", label="Neighbourhood profile", icon="gesix",
            thresholds={},   # shape-only, mirrors Berlin's `gesix_quiet` tile
            caveat=("Hamburg city rating of the ~2,200-resident block on "
                    "income, jobs, education, and family stability. "
                    "Reflects the block, not the specific building."),
        ),
    ),
)
