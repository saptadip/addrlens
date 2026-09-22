"""Berlin lens configs — Young Family + Newcomer + Quiet Living + Commuter tile lists.

Extracted from the flat `berlin.py` into a dedicated module so lens
changes touch only the lens file. The audience-hint prose, per-tile
threshold dicts, and caveat strings live here verbatim from the flat
file; only imports changed. Any LLM insight template that consumes a
tile's `slug`, `label`, `audience_hint`, or threshold dict is depending
on the exact strings here — DO NOT paraphrase.
"""
from app.cities.base import LensConfig, LensTileConfig


# --- Young Family lens (Spec A) --------------------------------------------
# Seven traffic-light tiles for families with kids under 6. Thresholds live
# per tile — every "why is this the tier" answer sits in one table here.
# Boundary convention: inclusive on the greener side (≤ green_m is green;
# > green_m is amber). See
# docs/superpowers/specs/2026-08-09-young-family-lens-design.md.
YOUNG_FAMILY_LENS: LensConfig = LensConfig(
    slug="young_family",
    label="Young Family (0–6)",
    audience_hint="For a family with kids under 6",
    tiles=(
        LensTileConfig(
            key="kita", label="Kita reachability", icon="kita",
            thresholds={"green_count": 3, "green_m": 400, "amber_m": 800},
        ),
        LensTileConfig(
            key="playground", label="Playground within stroller walk", icon="playground",
            thresholds={"green_m": 400, "amber_m": 800},
        ),
        LensTileConfig(
            key="pediatrician", label="Pediatrician within walk", icon="pediatrician",
            thresholds={"green_m": 800, "amber_m": 1500},
            caveat=("OSM community-tagged — inner-district coverage is good; "
                    "outer districts may under-report."),
        ),
        LensTileConfig(
            key="transit", label="Transit stop within walk", icon="transit",
            thresholds={"green_min": 5, "amber_min": 10},
            caveat=("Combines S-Bahn / U-Bahn / Tram (Berlin BOD + VBB) with the "
                    "nearest OSM-tagged bus stop. Tier is the shortest walk across "
                    "all four modes."),
        ),
        LensTileConfig(
            key="supermarket", label="Supermarket within walk", icon="cart",
            thresholds={"green_min": 5, "amber_min": 10},
            caveat=("OSM community-tagged — brand + hours coverage varies; "
                    "expect a small kiosk to look identical to a Rewe until you visit."),
        ),
        LensTileConfig(
            key="noise", label="Façade noise", icon="noise",
            thresholds={"green_db": 55, "amber_db": 60},
        ),
        LensTileConfig(
            key="heat", label="Summer heat", icon="heat",
            # Umweltatlas class strings — matched case-insensitively as substrings.
            thresholds={
                "green_classes": ("keine Belastung", "geringe Belastung"),
                "amber_classes": ("mäßige Belastung", "starke Belastung"),
            },
        ),
        LensTileConfig(
            key="air", label="Air quality (NO₂)", icon="air",
            # 20/40 tiers follow the app's existing NO₂ card thresholds
            # (§14.9 tier-color convention), not WHO 2021 strictly (10 μg/m³).
            thresholds={"green_ugm3": 20, "amber_ugm3": 40},
        ),
        LensTileConfig(
            key="refuge", label="Quiet / green refuge nearby", icon="refuge",
            # Composite: quiet zone distance OR crown coverage %. OR-forgiving
            # at both tiers so losing one signal still yields a real tier.
            #
            # Crown-coverage anchors retuned in sync with the Quiet Living
            # `street_trees` tile (PR #12) to reflect the Straßenbäume-only
            # physics. Berlin's Baumbestand tracks REGISTERED STREET TREES
            # ONLY, and the metric divides crown-disk area by whole-search-
            # disk area — real Berlin residential blocks rarely exceed the
            # low teens. The old 25 / 15 anchors were physically unreachable
            # via the canopy leg alone; the OR-with-quiet-zone leg was
            # carrying every green case in practice. Retuned to 10 / 5 so
            # both legs of the composite are actually reachable and an
            # address with 9% canopy + 500m quiet zone can now read green
            # via the canopy leg, matching the ground truth.
            thresholds={
                "green_quiet_m": 400,  "amber_quiet_m": 1000,
                "green_crown_pct": 10, "amber_crown_pct": 5,
            },
        ),
        LensTileConfig(
            key="gesix", label="Neighbourhood profile", icon="gesix",
            thresholds={},                       # quintiles derived from the Senate's own distribution
            caveat=("Senate GESIx 2022 composite — 20 employment / social / health "
                    "indicators aggregated per Planungsraum (~10k residents). "
                    "Reflects the polygon around your flat, not the individual "
                    "building. Refreshed by the Senate every 3–5 years."),
        ),
    ),
)

# --- Newcomer lens (Spec E) ------------------------------------------------
# Six traffic-light tiles for English-speaking expats in their first 90 days.
# Threshold convention: inclusive on the greener side (≤ green_m is green).
# See docs/superpowers/specs/2026-08-12-newcomer-lens-design.md.
NEWCOMER_LENS: LensConfig = LensConfig(
    slug="newcomer",
    label="Newcomer",
    audience_hint="First 90 days in Berlin — registration, transit, English-friendly services.",
    tiles=(
        LensTileConfig(
            key="buergeramt", label="Bürgeramt reach", icon="buergeramt",
            thresholds={"green_m": 1500, "amber_m": 3000},
        ),
        LensTileConfig(
            key="rail_transit", label="Rail Transit", icon="transit",
            thresholds={"sbahn_m": 800, "ubahn_m": 500, "any_rail_m": 1200},
        ),
        LensTileConfig(
            key="tram_transit", label="Tram Transit", icon="transit",
            thresholds={"green_m": 500, "amber_m": 1000},
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
            caveat="OSM community-tagged — inner-district coverage good, outer may under-report",
        ),
        LensTileConfig(
            key="language_school", label="German classes", icon="language_school",
            thresholds={"green_m": 1500, "amber_m": 3500},
            caveat="Covers VHS branches + private Sprachschulen tagged in OSM; small independent schools may be missing.",
        ),
        LensTileConfig(
            key="library", label="Public library", icon="library",
            thresholds={"green_m": 1000, "amber_m": 2500},
        ),
        LensTileConfig(
            key="packstation", label="Parcel pickup", icon="packstation",
            thresholds={"green_m": 400, "amber_m": 1000},
            caveat="DHL Packstation + Deutsche Post branches from OSM; DHL Packstation locker moves may take a few weeks to reflect.",
        ),
        LensTileConfig(
            key="parkzone", label="Resident parking", icon="parkzone",
            thresholds={"amber_edge_m": 400},
            caveat=("Berlin Parkraumbewirtschaftungszonen — Bezirks-"
                    "maintained paid-parking polygons. Green means either "
                    "inside a zone (residents get a Bewohnerparkausweis "
                    "for ~€10/yr with permit priority) or ≥400 m from any "
                    "zone (real free parking, typical in outer Berlin). "
                    "Amber means outside but close to a zone edge, where "
                    "visitor overflow floods your street without giving "
                    "you any priority."),
        ),
        LensTileConfig(
            key="wochenmarkt", label="Open market", icon="wochenmarkt",
            thresholds={"green_m": 800, "amber_m": 2000},
            caveat="Only permitted weekly markets; closures may take a season to disappear from the feed.",
        ),
        LensTileConfig(
            key="xmas_market", label="Christmas Market", icon="xmas_market",
            thresholds={"radius_m": 3000, "green_count": 2, "amber_count": 1},
            caveat=("Berlin Senate live GeoJSON of registered Weihnachtsmärkte. "
                    "Seasonal — the feed is populated Nov–Dec (~45–50 markets) "
                    "and thins to empty the rest of the year. Fetched once at "
                    "boot; restart the server to refresh."),
        ),
        LensTileConfig(
            key="nightlife_density", label="Nightlife density", icon="nightlife",
            thresholds={},   # numeric-only — no tier logic, no verdict
            caveat="Numeric only — no green/amber/red verdict. Dense nightlife is a positive for some newcomers and a negative for others; the noise tile covers the sound-level side of the same signal.",
        ),
        LensTileConfig(
            key="gesix_newcomer", label="Neighbourhood profile", icon="gesix",
            thresholds={},   # shape-only — no tier logic
        ),
    ),
)

# --- Quiet Living lens ------------------------------------------------------
# Nine tiles for someone who wants a calm, low-noise home. Noise + air are
# reused from the Young Family lens; refuge is split back into its two
# component signals (quiet zone + street trees) because a "quiet living"
# audience cares about each independently rather than an OR-forgiving
# composite. Three new tiles come from newly-wired Berlin WFS layers
# (Tempolimits, Übergeordnetes Straßennetz) and one from a reinterpreted
# use of the Newcomer nightlife bucket (inverted: fewer = better here).
# A tenth tile, `cobblestone_nearby`, was added later off the OSM
# surface-tag snapshot to score stone-road proximity as a noise proxy.
QUIET_LIVING_LENS: LensConfig = LensConfig(
    slug="quiet_living",
    label="Quiet Living",
    audience_hint="For someone who wants a calm, low-noise home",
    tiles=(
        LensTileConfig(
            key="noise", label="Façade noise", icon="noise",
            # Same boundaries as Young Family — WHO 55/60 dB L_DEN.
            thresholds={"green_db": 55, "amber_db": 60},
        ),
        LensTileConfig(
            key="air", label="Air quality (NO₂)", icon="air",
            thresholds={"green_ugm3": 20, "amber_ugm3": 40},
        ),
        LensTileConfig(
            key="quiet_zone", label="Nearest quiet zone", icon="refuge",
            thresholds={"green_m": 400, "amber_m": 1000},
            caveat=("Berlin 'Ruhige Gebiete' §47d BImSchG designation — "
                    "these zones combine acoustic quiet with recreation "
                    "value. Distance is to the polygon edge. State forests "
                    "(Grunewald, Tegeler Forst, Köpenicker Wald) and other "
                    "Landschaftsschutzgebiete are NOT on this list — they "
                    "are protected under Forstwirtschaft law rather than "
                    "§47d, so an address next to Grunewald Forst can still "
                    "read red here despite the objectively quiet reality."),
        ),
        LensTileConfig(
            key="street_trees", label="Street tree canopy", icon="refuge",
            # Retuned for a Straßenbäume-ONLY signal (Baumbestand data
            # covers registered street trees only, not park or private-
            # garden trees). Crown-coverage % is computed as the sum of
            # crown-disk areas divided by the SEARCH-DISK area. Because
            # street trees can physically only line curbs, the metric is
            # bounded above by the ratio of "tree strip along kerbs" to
            # "whole disk", which caps well under 20% even for tree-dense
            # residential streets. Concrete calibration:
            #
            #   Hufelandstr. 25 — Bötzowviertel core, both sides tree-lined
            #                     with mature Platanen/Ahorn, 199 registered
            #                     trees → 7.2% crown coverage.
            #
            # The original 25/15 cutoffs were inherited from YF's refuge
            # composite, where a low crown reading is rescued by the
            # `OR quiet-zone ≤400 m` leg. Standalone here, they made
            # green practically unreachable in Berlin. Retuned to 10/5
            # so that:
            #   green ≥10% = clearly tree-dense (Hufelandstr. tier)
            #   amber  ≥5% = some canopy present
            #   red   <5% = sparse / no street trees
            thresholds={"green_pct": 10, "amber_pct": 5},
        ),
        LensTileConfig(
            key="tempo30", label="Speed limit at your street", icon="tempo30",
            thresholds={"green_kmh": 30, "amber_kmh": 50, "default_kmh": 50},
            caveat=("Berlin's Tempolimits WFS lists EXCEPTIONS to the "
                    "general 50 km/h. Absence of a nearby exception is "
                    "reported as 'default 50 km/h', not unknown."),
        ),
        LensTileConfig(
            key="arterial_road", label="Distance to arterial road", icon="arterial_road",
            thresholds={"green_m": 150, "amber_m": 50},
            caveat=("Übergeordnetes Straßennetz Bestand — Berlin's "
                    "arterial + supra-local road network. Distance to "
                    "the nearest one is a rough proxy for exposure to "
                    "traffic noise and dust."),
        ),
        LensTileConfig(
            key="cobblestone_nearby", label="Cobblestone nearby", icon="cobblestone",
            # Distance-to-nearest, inverted (further = better). Green ≥ 100 m
            # is inaudible-indoors territory for a passing car at ~30 km/h
            # (60–65 dB at 10 m on `sett`, drops ~6 dB per distance doubling,
            # so ≥100 m is under the 40 dB WHO night-noise guideline). Amber
            # is the tolerable-but-audible band. Red < 30 m means the address
            # is on or immediately next to a cobblestone road — regular
            # nighttime car-passes will rattle.
            thresholds={"green_m": 100, "amber_m": 30},
            caveat=("OSM `highway=residential|unclassified|tertiary|"
                    "secondary|primary|living_street` AND `surface="
                    "sett|cobblestone|unhewn_cobblestone` on trafficked "
                    "roads only — cobble sidewalks (footway/pedestrian) "
                    "and `paving_stones` (mostly flat slab sidewalks) are "
                    "deliberately excluded. Way centroid is the query "
                    "anchor; short streets are ±150 m precise."),
        ),
        LensTileConfig(
            key="rail_noise", label="Rail-track proximity", icon="rail_noise",
            thresholds={"green_m": 400, "amber_m": 200},
            caveat=("Uses S-Bahn / U-Bahn station coordinates as a proxy "
                    "for track proximity. U-Bahn is treated as always "
                    "green because Berlin's U-Bahn is underground on "
                    "most sections; S-Bahn scales by distance."),
        ),
        LensTileConfig(
            key="nightlife_inverted", label="Nightlife within 300 m", icon="nightlife",
            thresholds={"radius_m": 300, "green_max": 3, "amber_max": 8},
            caveat=("Inverse of the Newcomer nightlife tile — fewer bars/"
                    "clubs/pubs within 300 m is greener here. Same OSM "
                    "data, opposite framing."),
        ),
        LensTileConfig(
            key="gesix_quiet", label="Neighbourhood profile", icon="gesix",
            thresholds={},   # shape-only, same pattern as gesix / gesix_newcomer
        ),
    ),
)

# --- Commuter lens ---------------------------------------------------------
# Nine tiles for a reader who needs a fast, reliable daily commute. Rail /
# tram / bus keys are commuter-specific (retuned thresholds vs Newcomer) so
# the AI-insight prompts can frame each mode as "daily starting point" not
# "reach for Anmeldung". Everything else uses the Index preloads that
# already exist for Young Family / Newcomer / Quiet Living.
COMMUTER_LENS: LensConfig = LensConfig(
    slug="commuter",
    label="Commuter",
    audience_hint="For someone who needs a fast, reliable daily commute.",
    tiles=(
        LensTileConfig(
            key="commuter_rail_transit", label="S+U-Bahn reach", icon="commuter_rail",
            # Tighter than Newcomer's 800/500/1200 — a commuter walking
            # 12 min twice a day loses 4+ hours per week to the walk.
            thresholds={"sbahn_m": 500, "ubahn_m": 500, "any_rail_m": 900},
        ),
        LensTileConfig(
            key="commuter_tram_transit", label="Tram reach", icon="transit",
            thresholds={"green_m": 400, "amber_m": 800},
        ),
        LensTileConfig(
            key="commuter_bus_transit", label="Bus reach", icon="transit",
            thresholds={"green_m": 250, "amber_m": 500},
        ),
        LensTileConfig(
            key="regional_rail_reach", label="Regional rail reach", icon="regional_rail",
            thresholds={"green_m": 1200, "amber_m": 2500},
            caveat=("Curated list of Berlin RE/RB stations. Doesn't cover "
                    "every S-Bahn stop the regional trains pass through; "
                    "the tile is 'which platform will your commuter train "
                    "actually stop at'."),
        ),
        LensTileConfig(
            key="cycling_network", label="Cycling network reach", icon="bike_network",
            thresholds={"green_m": 100, "amber_m": 300},
            caveat=("OSM `highway=cycleway` from the weekly Geofabrik "
                    "snapshot. Painted bike lanes on shared roads "
                    "(cycleway=lane on a `highway=residential`) are NOT "
                    "in this signal — only dedicated infrastructure."),
        ),
        LensTileConfig(
            key="parkzone", label="Resident parking", icon="parkzone",
            thresholds={"amber_edge_m": 400},
            caveat=("Berlin Parkraumbewirtschaftungszonen — Bezirks-"
                    "maintained paid-parking polygons. For car-owning "
                    "commuters: green inside a zone (Bewohnerparkausweis "
                    "priority) or well outside; amber at the edge of a "
                    "paid zone where visitor overflow competes for spots."),
        ),
        LensTileConfig(
            key="car_sharing_reach", label="Car-sharing reach", icon="car_sharing",
            thresholds={"radius_m": 500, "green_count": 3, "amber_count": 1},
            caveat=("Fixed pickup points from OSM community tags "
                    "(SHARE NOW / Miles / WeShare stations). Free-float "
                    "zones are NOT modelled — a station-based tile is "
                    "the honest signal."),
        ),
        LensTileConfig(
            key="ev_charging_reach", label="EV charger reach", icon="bolt",
            thresholds={"radius_m": 500, "green_count": 2, "amber_count": 1},
        ),
        LensTileConfig(
            key="airport_reach", label="Airport reach (BER)", icon="airport",
            thresholds={"green_km": 20, "amber_km": 35},
            caveat=("Straight-line distance to Berlin Brandenburg Airport. "
                    "Actual door-to-gate time depends on S9 / RE7 timing; "
                    "this tile is a rough exposure signal, not a routing."),
        ),
        LensTileConfig(
            key="gesix_commuter", label="Neighbourhood profile", icon="gesix",
            thresholds={},   # shape-only, same pattern as gesix / gesix_newcomer / gesix_quiet
        ),
    ),
)
