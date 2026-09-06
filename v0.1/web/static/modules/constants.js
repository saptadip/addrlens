import { ico } from './icons.js';

// Amenity catalogue: [key, label, icon, colour, optional-range-caption].
// Order below drives tile order on the Amenities/Medical tabs.
export const AMEN=[
  ['playgrounds','Playgrounds',ico.playground,'#22C55E'],
  ['parks','Parks / green space',ico.tree,'#10B981'],
  ['pharmacies','Pharmacies',ico.pharmacy,'#EF4444'],
  ['supermarkets','Supermarkets',ico.cart,'#F59E0B'],
  ['gps','Doctors',ico.gp,'#14B8A6'],
  ['hospitals','Hospitals',ico.hospital,'#DC2626','within ~2 km'],
  ['fountains','Drinking fountains',ico.fountain,'#0EA5E9'],
  ['ev_charging','EV charging',ico.bolt,'#EAB308'],
  ['transit','Transit stops',ico.transit,'#8B5CF6'],
  // Phase 1: /api/lookup-derived tiles bridged into the amenities pipeline
  // via _hydrateLookupTiles(). Same tile shape, click opens the same modal.
  // Street trees moved to Environment tab — its data is now displayed as a
  // full vertical card via streetTreesCardHtml() inside envExtraCardsHtml().
  ['swimSpots','Swim spots',ico.waves,'#0EA5E9','within 3 km'],
  ['fireRescue','Fire & rescue',ico.flame,'#DC2626','to nearest'],
];
export const AMEN_COLOR=Object.fromEntries(AMEN.map(([k,,,c])=>[k,c]));
// Which tab each category renders into. Default: 'amen'. Medical categories
// (pharmacies, GPs, hospitals, fireRescue) live under the Medical tab.
export const AMEN_TAB={pharmacies:'med', gps:'med', hospitals:'med', fireRescue:'med'};
export const tabOf=k=>AMEN_TAB[k]||'amen';

// -- Edu styling + noise tier labels ---------------------------------
export const EDU_STYLE={school:{icon:'school',color:'#4F46E5'},kita:{icon:'baby',color:'#94A3B8'},intl:{icon:'globe',color:'#F59E0B'}};
export const NOISE_TIER_LABEL={green:'Quiet',amber:'Moderate',orange:'Loud',red:'Very loud',unknown:'Unknown'};

// -- Life Mode / lens registry ---------------------------------------
export const LM_STATE_KEY  = 'berlin-lens-mode-v1';       // "on" | "off"
export const LM_SEEN_KEY   = 'berlin-lens-mode-seen-v1';  // "1" once seen or dismissed
export const LM_PULSE_MS   = 30000;                       // auto-stop pulse after 30 s
export const LM_ACTIVE_KEY  = 'berlin-lens-active-v1';    // "young_family"|"newcomer"
export const LM_DEFAULT_LENS = 'young_family';            // default for first-time users

export const LENS_TILE_EXPLANATIONS = {
  // Young Family lens
  kita:         "Distance to the nearest registered Kita AND count within a search radius, from Berlin's Kindertagesstätten BOD dataset. Green requires ≥ 3 kitas within 400 m walk; amber ≥ 1 within 800 m. Berlin's kita waitlists are long — proximity to several branches multiplies your shot at securing a spot.",
  playground:   "Distance to the nearest municipal playground (Grünanlagen — Spielplätze BOD + OSM). Green ≤ 400 m stroller walk; amber ≤ 800 m. For under-6s, frequency of use tracks proximity — a closer one gets visited every day, a further one becomes a weekend outing.",
  pediatrician: "Distance to the nearest OSM community-tagged pediatrician (Kinderarzt). Green ≤ 800 m walk; amber ≤ 1.5 km. First-time parents visit every 4–6 weeks in year one; walkable proximity beats waiting-list matching for a distant clinic.",
  transit:      "Walking time to the nearest S-Bahn / U-Bahn / Tram / Bus stop (VBB station coords + BVG Straßenbahnhaltestellen + OSM bus stops). Green ≤ 5 min stroller walk; amber ≤ 10 min. Stroller-tuned rather than commute-tuned — the walk speed assumed is slower and any mode reaching counts.",
  supermarket:  "Walking time to the nearest supermarket (OSM community-tagged). Green ≤ 5 min stroller walk; amber ≤ 10 min. Weekly grocery runs and last-minute nappy trips both compound around this distance.",
  refuge:       "Composite signal — the nearest §47d Ruhige Gebiet OR the street-tree canopy % from Berlin's Baumbestand around the flat. Green if quiet zone ≤ 400 m OR canopy ≥ 10 %; amber if quiet zone ≤ 1 km OR canopy ≥ 5 %. Answers 'can we walk somewhere calm' for daily park routines.",
  noise: "L_DEN is EU-standard day-evening-night noise averaging. WHO recommends ≤55 dB in residential areas; above 60 dB is linked to sleep disturbance.",
  heat:  "Berlin's Umweltatlas classifies each block's bioclimate (PET at 14:00 in summer). 'Belastung' = burden; higher classes indicate more heat stress.",
  air:   "NO₂ measured µg/m³ per street segment (Umweltatlas trend scenario). WHO 2021 annual guideline is 10 µg/m³; Germany's legal limit is 40.",
  gesix: "Berlin's Senate publishes a composite of 20 health, social and employment indicators per Planungsraum (~10k residents). Higher quintile = healthier / more stable neighbourhood context. The signal describes the polygon around the flat, not the building itself.",
  // Newcomer lens
  buergeramt:      "Distance to the nearest Bürgeramt (BOD Bezirks-Services). Green ≤ 1.5 km walk; amber ≤ 3 km. First-90-days visit cadence is high (Anmeldung, tax-ID, driver-license conversion) — a nearby branch saves cross-district trips.",
  rail_transit:    "Walking distance to the nearest S-Bahn AND U-Bahn station (VBB station-access dataset). Green requires S ≤ 800 m OR U ≤ 500 m. Newcomer-tuned for intercity trips (Hauptbahnhof) and airport runs (BER via S9 / RE7), not daily commute — the Commuter lens applies tighter thresholds.",
  tram_transit:    "Walking distance to the nearest tram stop (BVG Straßenbahnhaltestellen dataset). Green ≤ 500 m walk; amber ≤ 1 km. Trams fill the last-mile gap between S/U hub and home in former East Berlin; West Berlin has essentially no active tram network.",
  bus_transit:     "Walking distance to the nearest bus stop (OSM `highway=bus_stop` via weekly Geofabrik snapshot). Green ≤ 300 m walk; amber ≤ 600 m. Bus covers routes S/U/Tram skip, and N-line night buses run after the 01:30 rail shutdown on weekdays.",
  intl_food:       "Count of international-cuisine venues within 1 km (OSM tagged Vietnamese, Middle Eastern, Italian, Turkish and similar). Green ≥ 6 within 1 km; amber ≥ 2. Familiar-cuisine anchors in walkable distance make a neighbourhood feel like home faster.",
  coworking:       "Count of coworking spaces and laptop-friendly cafés within 1 km (OSM `office=coworking` + tagged cafés). Green ≥ 3; amber ≥ 1. Having multiple options avoids the single-spot problem when the Wi-Fi's down or the seat's taken.",
  english_clinic:  "Distance to the nearest OSM-tagged English-language-friendly clinic. Green ≤ 1 km walk; amber ≤ 3 km. Newcomers without B1 German need at least one nearby clinic where consultations run in English.",
  gesix_newcomer: "How this Planungsraum sits on Berlin's 2022 GESIx socioeconomic band. Lower and higher quintiles both come with real tradeoffs for a newcomer — language mix, rent band, mutual-aid density — so walk the block before you sign.",
  language_school: "Walking distance to the nearest Sprachschule or Volkshochschule (VHS) branch. Green ≤ 1.5 km walk; amber ≤ 3.5 km. B1 German is the practical gate to Aufenthaltstitel and Einbürgerung — course finish rates track attendance, and attendance tracks how close class is to home.",
  library: "Distance to the nearest public library (VÖBB) or university library. Green ≤ 1 km walk; amber ≤ 2.5 km. For newcomers the library is the lowest-friction 'third place' — free Wi-Fi, warm study space, English fiction, integration events, no purchase pressure.",
  packstation: "Distance to the nearest DHL Packstation locker or Deutsche Post branch. Green ≤ 400 m walk; amber ≤ 1 km. Germany's parcel logistics assume you can retrieve mis-timed deliveries; a long walk turns weekly pickups into a chore.",
  wochenmarkt: "Distance to the nearest permitted Wochenmarkt. Green ≤ 800 m walk; amber ≤ 2 km. Cash-friendly, no-German-required, international vendors — a weekly market makes the neighbourhood feel like home faster than any single supermarket run.",
  nightlife_density: "Count of tagged bars, pubs, and nightclubs within a 1 km walk (OSM community-tagged, via the weekly Geofabrik snapshot). Numeric-only — no green / amber / red verdict. Berlin's nightlife is famously part of its draw, but the same density is what can turn a bedroom window into a night-noise complaint.",
  // Quiet Living lens explanations.
  gesix_quiet: "How this Planungsraum sits on Berlin's 2022 GESIx socioeconomic band, read for a quiet-living audience. Quintile 1 areas trend residential and quieter at night; quintile 5 areas trend denser with weekend nightlife audible from residential windows. The signal describes the polygon around the flat — walk the block after 22:00 before signing.",
  quiet_zone:   "Berlin's 'Ruhige Gebiete' are legally designated under §47d BImSchG — meant to be protected from noise, not just labelled green space. Distance is to the polygon edge; short walks make a real difference to weekly noise recovery. State forests (Grunewald, Tegeler Forst, Köpenicker Wald) and other Landschaftsschutzgebiete are NOT on this list — they're protected under Forstwirtschaft law instead — so an address next to a big forest can read red here despite abundant nearby quiet.",
  street_trees: "Street-tree canopy percentage in a bounding box around the flat, from Berlin's Baumbestand. Green ≥ 10 % crown coverage; amber ≥ 5 %. Dense mature canopy buffers road noise, drops summer heat, and softens the acoustic feel of the block outside the door.",
  tempo30: "Berlin's Tempolimits WFS lists exceptions to the general 50 km/h — Tempo-30 zones, 40, 60, Autobahn limits. Green if the local order is ≤ 30 km/h; amber up to 50 km/h; red above 50. Perceived road noise roughly doubles per +10 km/h at street level, so a Tempo-30 order at your door is a material win.",
  arterial_road: "Distance to the nearest arterial from the Übergeordnetes Straßennetz Bestand — Berlin's supra-local road network. INVERTED signal — further is better. Green ≥ 150 m away; amber ≥ 50 m; red inside 50 m. A rough proxy for exposure to steady traffic noise, night-time truck passes, and pram-unfriendly pavements.",
  rail_noise: "Distance to the nearest S/U-Bahn station as a proxy for track proximity. INVERTED signal — further is better. Green ≥ 400 m away; amber ≥ 200 m; red inside 200 m. S-Bahn is above-ground and generates real façade noise; Berlin's U-Bahn is underground on most sections, so U-nearest reads greener regardless of walking distance.",
  nightlife_inverted: "Same OSM bar/club count as the Newcomer nightlife tile, but the framing is inverted here: fewer venues within 300 m is greener. Green ≤ 3 venues within 300 m; amber ≤ 8; red above 8. Nightlife density predicts weekend and night-time street noise better than any daytime traffic count.",
  // Commuter lens explanations. Voice follows YF / Newcomer / QL:
  // lead with WHAT dataset the tile reads and HOW it's measured, close
  // with a short audience note. Rail/tram/bus share their feed with the
  // Newcomer transit tiles (VBB / BVG / OSM) but use tighter thresholds
  // for the daily-commute framing.
  commuter_rail_transit: "Walking distance to the nearest S-Bahn and U-Bahn station, from VBB's Koordinaten der Zugangsmöglichkeiten (station-access dataset). Green requires either S ≤ 500 m or U ≤ 500 m — tighter than the Newcomer rail tile's 800 m — because twice-daily walk time compounds across the working week.",
  commuter_tram_transit: "Walking distance to the nearest tram stop, from BVG's Straßenbahnhaltestellen dataset (Ungestörtes ÖPNV-Netz). Green threshold is 400 m — tighter than the Newcomer tram tile's 500 m. Berlin's tram network is concentrated in former East Berlin (Mitte, Friedrichshain, Prenzlauer Berg, Lichtenberg, Marzahn); West Berlin removed most of its lines 1954–67, so this tile often reads red west of the S1 corridor.",
  commuter_bus_transit:  "Walking distance to the nearest bus stop, from OpenStreetMap's community-tagged `highway=bus_stop` layer (via the weekly Geofabrik snapshot). Green threshold is 250 m — tighter than the Newcomer bus tile's 300 m — reflecting the daily cost of a longer walk twice a day.",
  regional_rail_reach:   "Walking distance to the nearest curated RE/RB regional-rail station. Berlin has ~15 inner-ring platforms served by regional trains (Alexanderplatz, Friedrichstraße, Potsdamer Platz, Hauptbahnhof, Ostbahnhof, Südkreuz, Ostkreuz, etc.). Green threshold is 1200 m — longer than S/U — because RE/RB headways run 20–60 min and missing a train costs more than missing an S-Bahn.",
  cycling_network:       "Distance to dedicated cycleway infrastructure (OSM highway=cycleway). Green ≤ 100 m walk; amber ≤ 300 m. Painted bike lanes on shared roads are NOT in this signal — the tile measures 'protected cycleway near door', which is the single biggest quality signal for daily bike commuting in Berlin.",
  car_sharing_reach:     "Count of fixed car-sharing pickup points within 500 m (OSM amenity=car_sharing — SHARE NOW / Miles / WeShare stations). Green ≥ 3 stations within 500 m; amber ≥ 1. Free-float zones are NOT modelled. A cluster of nearby stations makes occasional car access practical for the weekly IKEA run or a weekend trip out of the city.",
  ev_charging_reach:     "Count of public EV chargers within 500 m (OSM). Green ≥ 2 within 500 m; amber ≥ 1. Matters mainly if you commute with an electric car and don't have home charging — overnight top-ups at a nearby street charger keep the daily commute practical. OSM coverage and public/private status are uneven; confirm on the operator's app before relying on a specific station.",
  airport_reach:         "Straight-line distance from the flat to Berlin Brandenburg Airport (BER). Green ≤ 20 km; amber ≤ 35 km. For frequent flyers this compounds — shorter departure buffers, easier evening arrivals. Real door-to-gate time depends on the S9 or RE7 schedule, not on crow-flight distance alone; a nearby airport also carries a noise trade-off covered by the Quiet Living lens.",
  gesix_commuter:        "How this Planungsraum sits on Berlin's 2022 GESIx socioeconomic band, read for a daily commuter. Quintile 1 polygons often sit further from the S/U network (the tradeoff for residential quiet); quintile 5 polygons often sit ON it (the tradeoff for daily density and peak-hour platform crowding).",
};

export const GLOSSARY = {
  'Kita': "Short for 'Kindertagesstätte' — the German name for a daycare centre serving children roughly 0–6 years old. Spots are limited; families often reserve one during pregnancy.",
  'Kinderarzt': "German for pediatrician — a doctor specialising in children's health. Most public health-insurance plans (gesetzliche Krankenkasse) pay for regular check-ups from birth through age ~18; parents book directly with a Kinderarzt of their choice.",
  'S-Bahn': "Berlin's mostly above-ground suburban rail network. Trains run every 5–20 minutes and share a single ticket with the U-Bahn. Blue-and-white 'S' logo on a green disk.",
  'U-Bahn': "Berlin's mostly underground metro network. Trains every 3–10 minutes on most lines. Blue-and-white 'U' logo on a blue disk.",
  'Tram': "Berlin's tram (streetcar) network — the German name is Straßenbahn. Concentrated in former East Berlin (Mitte, Prenzlauer Berg, Friedrichshain, Lichtenberg); West Berlin removed most of its trams by 1967.",
  'Straßenbahn': "German for tram / streetcar. Same network as the 'Tram' entry.",
  'Straßenbahnhaltestellen': "Tram stops (literally 'streetcar stopping-places'). The name of the BVG dataset that lists every operational tram stop in Berlin.",
  'BVG': "Berliner Verkehrsbetriebe — the company that runs Berlin's U-Bahn, tram, bus, and ferry network. Not to be confused with the S-Bahn (a different operator).",
  'VBB': "Verkehrsverbund Berlin-Brandenburg — the regional transit union. One ticket works across S-Bahn, U-Bahn, tram, bus, and regional rail in Berlin plus the surrounding Brandenburg state.",
  'ÖPNV': "Öffentlicher Personennahverkehr — 'public local passenger transport'. Umbrella German term covering S-Bahn, U-Bahn, tram, and bus service.",
  'Ungestörtes ÖPNV-Netz': "'Undisturbed public-transit network' — BVG's data set of its own transit stops (U-Bahn, tram, bus, ferry) merged into one inventory. The 'ungestört' part refers to the network being represented without traffic-simulation overlays.",
  'Regionalbahn': "Regional rail — trains connecting Berlin to surrounding Brandenburg towns (Potsdam, Bernau, Erkner). Two service classes: RE (Regional-Express, fewer stops) and RB (Regionalbahn, more stops).",
  'Hauptbahnhof': "Berlin's main train station, opened 2006. Central hub for intercity trains (ICE, IC) and regional rail (RE, RB). Located north of the Reichstag.",
  'L_DEN': "EU-standard 24-hour noise average, weighted higher for evening and night to reflect sleep-disturbance impact. Measured in decibels (dB). WHO recommends ≤ 55 dB in residential areas.",
  'L_night': "Night-time noise average, 22:00–06:00. Measured in decibels (dB). WHO recommends ≤ 40 dB in residential areas for undisturbed sleep.",
  'Belastung': "German for 'burden' or 'stress'. Used by Berlin's Umweltatlas to grade environmental exposure. Bands: keine (none), geringe (low), mäßige (moderate), starke (strong), extreme (extreme).",
  'Umweltatlas': "Berlin's Environmental Atlas — a municipal open-data mapping of air quality, noise, heat, groundwater, vegetation, and other environmental signals. Refreshed by the Senate on a rolling basis.",
  'PET': "Physiological Equivalent Temperature — a heat-stress metric that combines air temperature, humidity, wind, and solar radiation. Used to grade a block's summertime bioclimate.",
  'Ruhige Gebiete': "Berlin's legally designated quiet zones under §47d BImSchG. Roughly 50 urban parks specifically protected from noise. State forests (Grunewald, Tegeler Forst) are NOT on this list — they're protected under Forstwirtschaft law instead.",
  '§47d BImSchG': "Section 47d of the German Federal Immission Control Act (Bundes-Immissionsschutzgesetz). Requires municipalities to designate 'quiet zones' meant to protect recreation areas from noise.",
  'BImSchG': "Bundes-Immissionsschutzgesetz — Germany's Federal Immission Control Act. The law that regulates emissions, noise, and other environmental pollutants.",
  'Landschaftsschutzgebiete': "Landscape protection areas — a German legal designation protecting landscape character and biodiversity (e.g. Grunewald). Different from Ruhige Gebiete: Landschaftsschutzgebiete protect scenery, Ruhige Gebiete specifically protect quiet.",
  'Forstwirtschaft': "German forestry law — the legal category under which state forests like Grunewald and Tegeler Forst are protected. Not the same as §47d quiet zones.",
  'Baumbestand': "Berlin's municipal tree register — an open-data inventory of every registered street tree, with species, age, crown diameter, and location.",
  'Straßenbäume': "Street trees — trees planted along public streets by the city. Registered in the Baumbestand. Does NOT include park trees or private-garden trees.",
  'Planungsraum': "Berlin's smallest official planning unit — roughly 7,500 residents each. Berlin has ~540 Planungsräume (raised from ~447 in the 2021 LOR boundary reform). GESIx and many other municipal statistics are reported at this level.",
  'GESIx': "Berlin's socioeconomic index — a composite score of 20+ health, social, and employment indicators aggregated per Planungsraum. Higher quintile = healthier / more stable neighbourhood context.",
  'Kiez': "Berlin slang for a small neighbourhood or block district — the few streets around your flat where you know the corner store, the bakery, the local park.",
  'Bezirk': "One of Berlin's 12 official boroughs (Mitte, Kreuzberg, Pankow, etc.). Each administered by its own Bezirksamt (borough office).",
  'Bürgeramt': "Berlin's citizens' registration office. Where you go for Anmeldung, passport renewal, driver's license, and other civic services. Berlin has ~46 branches.",
  'Anmeldung': "Mandatory address registration for anyone living in Germany. Must be done at a Bürgeramt within 14 days of moving. Required for opening a bank account, getting a health card, and most basic services.",
  'Aufenthaltstitel': "German residence permit — the visa document that lets non-EU citizens live and work in Germany. Requires Anmeldung, health insurance, and (for many types) B1-level German.",
  'Einbürgerung': "German naturalization — the process of becoming a German citizen. Usually requires 5–8 years of residence, B1 German, financial self-sufficiency, and passing a civics test.",
  'Sprachschule': "German language school — private course provider. Most offer A1–C2 courses, often intensive (20 hrs/week) for students on a language visa.",
  'Volkshochschule': "Adult education centre (VHS) — one per Bezirk. The cheapest German-course option in Berlin. Also offers cooking, art, and civics classes.",
  'VÖBB': "Verbund Öffentlicher Bibliotheken Berlins — Berlin's public library network. A single €10/year card gives access to 80+ branches across all 12 Bezirke.",
  'Bibliothek': "German for library. Berlin's public library network is called VÖBB.",
  'Packstation': "DHL's parcel-locker network — where packages get delivered when you're not home. Uses a PIN or app to open. Named 'Packstation' (yes, that's the actual German name).",
  'Deutsche Post': "Germany's national postal service. Runs Packstation and has staffed post branches (Postfilialen) at many corner shops.",
  'Wochenmarkt': "Weekly outdoor market — typically Wednesday or Saturday. Vendors sell fruits, vegetables, cheese, bread, flowers. Cash-friendly, usually no German required.",
  'Übergeordnetes Straßennetz': "Berlin's 'supra-local road network' — the register of major arterials (Ku'damm, Karl-Marx-Allee, Frankfurter Allee, etc.). These are the cross-city routes; residential streets branch off.",
  'Tempolimits': "Berlin's speed-limit dataset — a live map of every exception to the general 50 km/h city limit. Tempo-30 zones dominate residential streets.",
  'Tempo-30': "30 km/h zone — a residential street where the speed limit is 30 km/h instead of the default 50. Reduces noise noticeably and cuts pedestrian-collision severity.",
  'Autobahn': "German motorway. In Berlin, the A100 city motorway ring and the A111/A113/A114/A115 spokes. Rural sections often have no general speed limit.",
  'Grünanlagen': "Green spaces — Berlin's municipal category for parks, playgrounds, and other public open spaces.",
  'Spielplätze': "Playgrounds. Berlin's Grünanlagen — Spielplätze dataset lists every registered municipal playground.",
};

// Tile → glossary keys. Only add words that actually surface in that tile's
// caveat / explanation / sources / dataset name. Empty list = no glossary
// section rendered for that tile.
export const TILE_GLOSSARY_KEYS = {
  // Young Family
  kita:                  ['Kita', 'Bezirk'],
  playground:            ['Grünanlagen', 'Spielplätze'],
  pediatrician:          ['Kinderarzt'],
  transit:               ['S-Bahn', 'U-Bahn', 'Tram', 'Straßenbahn', 'BVG', 'VBB'],
  supermarket:           [],
  noise:                 ['L_DEN', 'L_night', 'Belastung'],
  heat:                  ['Belastung', 'Umweltatlas', 'PET'],
  air:                   ['Umweltatlas'],
  refuge:                ['Ruhige Gebiete', '§47d BImSchG', 'Baumbestand', 'Straßenbäume'],
  gesix:                 ['Planungsraum', 'GESIx', 'Kiez', 'Bezirk'],
  // Newcomer
  buergeramt:            ['Bürgeramt', 'Anmeldung', 'Aufenthaltstitel'],
  rail_transit:          ['S-Bahn', 'U-Bahn', 'Hauptbahnhof', 'VBB'],
  tram_transit:          ['Tram', 'Straßenbahn', 'BVG', 'VBB'],
  bus_transit:           ['BVG', 'S-Bahn', 'U-Bahn', 'Tram'],
  intl_food:             [],
  coworking:             [],
  english_clinic:        [],
  language_school:       ['Sprachschule', 'Volkshochschule', 'Aufenthaltstitel', 'Einbürgerung'],
  library:               ['VÖBB', 'Bibliothek', 'Bezirk'],
  packstation:           ['Packstation', 'Deutsche Post'],
  wochenmarkt:           ['Wochenmarkt'],
  nightlife_density:     [],
  gesix_newcomer:        ['Planungsraum', 'GESIx', 'Kiez', 'Bezirk'],
  // Quiet Living
  quiet_zone:            ['Ruhige Gebiete', '§47d BImSchG', 'BImSchG', 'Landschaftsschutzgebiete', 'Forstwirtschaft'],
  street_trees:          ['Baumbestand', 'Straßenbäume'],
  tempo30:               ['Tempo-30', 'Tempolimits', 'Autobahn'],
  arterial_road:         ['Übergeordnetes Straßennetz'],
  rail_noise:            ['S-Bahn', 'U-Bahn'],
  nightlife_inverted:    [],
  gesix_quiet:           ['Planungsraum', 'GESIx', 'Kiez', 'Bezirk'],
  // Commuter
  commuter_rail_transit: ['S-Bahn', 'U-Bahn', 'VBB'],
  commuter_tram_transit: ['Straßenbahn', 'BVG', 'Straßenbahnhaltestellen', 'Ungestörtes ÖPNV-Netz', 'ÖPNV'],
  commuter_bus_transit:  [],
  regional_rail_reach:   ['Regionalbahn', 'VBB'],
  cycling_network:       [],
  car_sharing_reach:     [],
  ev_charging_reach:     [],
  airport_reach:         ['S-Bahn', 'Regionalbahn'],
  gesix_commuter:        ['Planungsraum', 'GESIx', 'Kiez', 'Bezirk'],
};

// -- Spec D: map-pin colour per tier --------------------------------
export const TIER_PIN_COLORS = {
  green:   '#22C55E',   // matches --success
  amber:   '#F59E0B',   // matches --amber
  red:     '#EF4444',   // matches --danger
  unknown: '#9CA3AF',
};

// v0.1 lens registry — add a new lens as a row here and the picker + tab
// switching flow picks it up automatically. Bureaucracy is intentionally
// omitted (moved to raw-mode 'Others' tab per user spec).
export const LIFE_MODE_LENSES = [
  {slug: 'young_family', label: 'Young Family',
   icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="7" r="2.5"/><path d="M4 21v-4a5 5 0 0 1 10 0v4"/><circle cx="17" cy="10" r="1.8"/><path d="M13.5 21v-3a3 3 0 0 1 6 0v3"/></svg>'},
  {slug: 'newcomer', label: 'Newcomer',
   icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="3.5"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/><path d="M17 4l3 3-3 3"/><path d="M14 7h6"/></svg>'},
  {slug: 'quiet_living', label: 'Quiet Living',
   // Placeholder headphones-shape icon — production SVG lands with the
   // frontend UI PR that also styles the three new tile icons
   // (tempo30, arterial_road, rail_noise).
   icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14v-2a8 8 0 0 1 16 0v2"/><path d="M4 14h3v6H4a2 2 0 0 1-2-2v-2a2 2 0 0 1 2-2z"/><path d="M20 14h-3v6h3a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2z"/></svg>'},
  {slug: 'commuter', label: 'Commuter',
   // Placeholder train-and-track icon — the Phosphor-style production
   // SVGs for the 8 new commuter tile icons (commuter_rail, transit,
   // regional_rail, bike_network, car_sharing, bolt, airport, gesix)
   // land with the frontend polish PR that follows this ship.
   icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 12h14"/><circle cx="9" cy="15" r="1"/><circle cx="15" cy="15" r="1"/><path d="M8 21l-2 2M16 21l2 2"/></svg>'},
  // Future: {slug: 'student', label: 'Student', icon: '<svg>…</svg>'},
  // Future: {slug: 'senior',  label: 'Senior',  icon: '<svg>…</svg>'},
];

// -- Card drag-reorder key ------------------------------------------
export const CARD_ORDER_KEY = 'addrlens.cardOrder.v1';

// -- Connectivity tile meta ------------------------------------------
export const CONN_META = {
  sbahn:         {label:'S-Bahn',        note:'Regional rapid transit'},
  ubahn:         {label:'U-Bahn',        note:'Subway'},
  tram:          {label:'Tram',          note:'Straßenbahn'},
  regional_rail: {label:'Regional rail', note:'RE / RB — DB Regio'},
  bus:           {label:'Bus',           note:'BVG bus stop'},
  airport:       {label:'Airport',       note:'International'},
};

// -- Compare board ---------------------------------------------------
export const COMPARE_KEY='berlin-lens-compare-v1'; export const COMPARE_MAX=5;

// -- Title-case small-word set --------------------------------------
export const _TITLE_SMALL = new Set([
  'a','an','the','and','but','or','nor','for','so','yet',
  'at','by','in','of','on','to','up','as','per','via','with','from','into','over','than'
]);

// -- Lens AI panel constants -----------------------------------------
export const _LENS_WITH_AI = new Set(['young_family', 'newcomer', 'quiet_living', 'commuter']);

export const _ICON_DOWNLOAD = '<svg viewBox="0 0 256 256" aria-hidden="true"><path d="M216,144v64a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8V144a8,8,0,0,1,8-8H88l40,40,40-40h40A8,8,0,0,1,216,144Z" opacity="0.2"/><path d="M216,144v64a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8V144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><polyline points="88 112 128 152 168 112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="40" x2="128" y2="152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>';
