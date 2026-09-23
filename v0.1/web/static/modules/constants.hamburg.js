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
export const LM_STATE_KEY  = 'hamburg-lens-mode-v1';       // "on" | "off"
export const LM_SEEN_KEY   = 'hamburg-lens-mode-seen-v1';  // "1" once seen or dismissed
export const LM_PULSE_MS   = 30000;                        // auto-stop pulse after 30 s
export const LM_ACTIVE_KEY  = 'hamburg-lens-active-v1';    // "newcomer"|"commuter"
export const LM_DEFAULT_LENS = 'newcomer';                 // Hamburg ships newcomer + commuter only

export const LENS_TILE_EXPLANATIONS = {
  // Newcomer lens
  rail_transit:    "Walking distance to the nearest S-Bahn AND U-Bahn station (HVV station-access dataset). Green requires S ≤ 800 m OR U ≤ 500 m. Newcomer-tuned for intercity trips (Hamburg-Hauptbahnhof) and airport runs (HAM via S1), not daily commute — the Commuter lens applies tighter thresholds.",
  bus_transit:     "Walking distance to the nearest bus stop (OSM `highway=bus_stop` via weekly Geofabrik snapshot). Green ≤ 300 m walk; amber ≤ 600 m. HVV bus covers routes S/U skip; MetroBus and express lines run frequent daytime service. Night buses cover the city after the late-night rail window.",
  ferry_transit:   "Walking distance to the nearest HADAG ferry pier. Green ≤ 500 m; amber ≤ 1 km. HVV-integrated; all-day service on lines 62, 64, 72; other lines are peak-only. Ferries carry bikes.",
  intl_food:       "Count of international-cuisine venues within 1 km (OSM tagged Vietnamese, Middle Eastern, Italian, Turkish and similar). Green ≥ 6 within 1 km; amber ≥ 2. Familiar-cuisine anchors in walkable distance make a neighbourhood feel like home faster.",
  coworking:       "Count of coworking spaces and laptop-friendly cafés within 1 km (OSM `office=coworking` + tagged cafés). Green ≥ 3; amber ≥ 1. Having multiple options avoids the single-spot problem when the Wi-Fi's down or the seat's taken.",
  english_clinic:  "Distance to the nearest OSM-tagged English-language-friendly clinic. Green ≤ 1 km walk; amber ≤ 3 km. Newcomers without B1 German need at least one nearby clinic where consultations run in English.",
  language_school: "Walking distance to the nearest Sprachschule or Volkshochschule (VHS) branch. Green ≤ 1.5 km walk; amber ≤ 3.5 km. B1 German is the practical gate to Aufenthaltstitel and Einbürgerung — course finish rates track attendance, and attendance tracks how close class is to home.",
  library: "Distance to the nearest Bücherhallen Hamburg branch or university library. Green ≤ 1 km walk; amber ≤ 2.5 km. For newcomers the library is the lowest-friction 'third place' — free Wi-Fi, warm study space, English fiction, integration events, no purchase pressure.",
  packstation: "Distance to the nearest DHL Packstation locker or Deutsche Post branch. Green ≤ 400 m walk; amber ≤ 1 km. Germany's parcel logistics assume you can retrieve mis-timed deliveries; a long walk turns weekly pickups into a chore.",
  parkzone: "Point-in-polygon check against Hamburg's Bewohnerparkgebiete (Bewohnerparken polygon layer, Hamburg Open Data). Two-tier signal, resident-friendly framing. Green when the address is inside a zone (residents can apply for a Bewohnerparkausweis) OR when it's ≥ 400 m from any zone edge (real free parking, typical in outer Hamburg). Amber when outside but within 400 m of a zone edge — visitor overflow floods your street without giving you permit priority. WFS layer does not carry fee/enforcement hours.",
  nightlife_density: "Count of tagged bars, pubs, and nightclubs within a 1 km walk (OSM community-tagged, via the weekly Geofabrik snapshot). Numeric-only — no green / amber / red verdict. Hamburg's nightlife (Reeperbahn, Schanzenviertel) is part of its draw, but the same density can turn a bedroom window into a night-noise complaint.",
  sozialmonitoring_status: "What Hamburg's city government says about this address's block. Every small neighbourhood (~2,200 residents) gets a yearly rating on income, jobs, education, and family stability — a snapshot of how the area is doing. Your address inherits the block's rating: strong, average, stretched, or under strain. Reflects the block, not your specific building.",
  sozialmonitoring_gesamt: "A city-support label — not a warning. Hamburg tags neighbourhoods that either need extra social investment right now, OR are trending in the wrong direction, as areas for city focus. This tile tells you whether your address falls inside one of those tagged areas. Independent from the neighbourhood-status tile — a well-off block can still be tagged if it's trending down.",
  // Commuter lens explanations. Voice follows Newcomer: lead with WHAT dataset
  // the tile reads and HOW it's measured, close with a short audience note.
  // Rail/bus share their feed with Newcomer transit tiles (HVV / OSM) but use
  // tighter thresholds for the daily-commute framing.
  commuter_rail_transit: "Walking distance to the nearest S-Bahn and U-Bahn station, from HVV's station-access dataset. Green requires either S ≤ 500 m or U ≤ 500 m — tighter than the Newcomer rail tile's 800 m — because twice-daily walk time compounds across the working week.",
  commuter_bus_transit:  "Walking distance to the nearest bus stop, from OpenStreetMap's community-tagged `highway=bus_stop` layer (via the weekly Geofabrik snapshot). Green threshold is 250 m — tighter than the Newcomer bus tile's 300 m — reflecting the daily cost of a longer walk twice a day.",
  commuter_ferry_transit: "Walking distance to the nearest HADAG pier, retuned for a daily commuter. Green ≤ 400 m; amber ≤ 800 m. All-day lines: 62, 64, 72. HVV ticket covers both S/U and ferry.",
  regional_rail_reach:   "Walking distance to the nearest curated RE/RB regional-rail station. Hamburg has several inner-city platforms served by regional trains (Hauptbahnhof, Dammtor, Altona, Harburg, Bergedorf, etc.). Green threshold is 1200 m — longer than S/U — because RE/RB headways run 20–60 min and missing a train costs more than missing an S-Bahn.",
  cycling_network:       "Distance to dedicated cycleway infrastructure (OSM highway=cycleway). Green ≤ 100 m walk; amber ≤ 300 m. Painted bike lanes on shared roads are NOT in this signal — the tile measures 'protected cycleway near door', which is the single biggest quality signal for daily bike commuting in Hamburg.",
  car_sharing_reach:     "Count of fixed car-sharing pickup points within 500 m (OSM amenity=car_sharing — station-based schemes). Green ≥ 3 stations within 500 m; amber ≥ 1. Free-float zones are NOT modelled. A cluster of nearby stations makes occasional car access practical for the weekly IKEA run or a weekend trip.",
  ev_charging_reach:     "Count of public EV chargers within 500 m (OSM). Green ≥ 2 within 500 m; amber ≥ 1. Matters mainly if you commute with an electric car and don't have home charging — overnight top-ups at a nearby street charger keep the daily commute practical. OSM coverage and public/private status are uneven; confirm on the operator's app before relying on a specific station.",
  airport_reach:         "Straight-line distance from the flat to Hamburg Airport (HAM). Green ≤ 12 km; amber ≤ 22 km. For frequent flyers this compounds — shorter departure buffers, easier evening arrivals. Real door-to-gate time depends on the S1 schedule (S-Bahn direct to HAM) plus check-in lead time, not on crow-flight distance alone.",
  sozialmonitoring_status_commuter: "Same signal as the Newcomer Neighbourhood status tile — commuter-audience framing.",
  sozialmonitoring_gesamt_commuter: "Same signal as the Newcomer City focus area tile — commuter-audience framing.",
};

export const GLOSSARY = {
  'Kita': "Short for 'Kindertagesstätte' — the German name for a daycare centre serving children roughly 0–6 years old. Spots are limited; families often reserve one during pregnancy.",
  'Kinderarzt': "German for pediatrician — a doctor specialising in children's health. Most public health-insurance plans (gesetzliche Krankenkasse) pay for regular check-ups from birth through age ~18; parents book directly with a Kinderarzt of their choice.",
  'S-Bahn': "Hamburg's suburban rail network (HVV). Trains run every 5–20 minutes and share a single HVV ticket with the U-Bahn and ferry. Direct S-Bahn link to Hamburg Airport (HAM) via S1. Green disk with white 'S'.",
  'U-Bahn': "Hamburg's urban metro network, operated by HHA (Hamburger Hochbahn). Four lines (U1–U4). Trains every 3–10 minutes on most lines. White 'U' on a blue disk.",
  'HVV': "Hamburger Verkehrsverbund — Hamburg's regional transit authority. One HVV ticket covers S-Bahn, U-Bahn, HADAG ferry, and bus within the fare zones.",
  'HADAG': "HADAG Seetouristik und Fährdienst — Hamburg's public ferry operator on the Elbe. Lines 62, 64, 72 run all day; other lines are peak-only or seasonal. HVV-integrated; bikes travel free.",
  'ÖPNV': "Öffentlicher Personennahverkehr — 'public local passenger transport'. Umbrella German term covering S-Bahn, U-Bahn, ferry, and bus service.",
  'Regionalbahn': "Regional rail — trains connecting Hamburg to surrounding towns and states. Two service classes: RE (Regional-Express, fewer stops) and RB (Regionalbahn, more stops). Covered by HVV within Hamburg fare zones.",
  'Hamburg-Hauptbahnhof': "Hamburg's main train station — the busiest in Germany by passenger count. Central hub for intercity trains (ICE, IC), regional rail (RE, RB), S-Bahn, and U-Bahn. Located in the city centre.",
  'L_DEN': "EU-standard 24-hour noise average, weighted higher for evening and night to reflect sleep-disturbance impact. Measured in decibels (dB). WHO recommends ≤ 55 dB in residential areas.",
  'L_night': "Night-time noise average, 22:00–06:00. Measured in decibels (dB). WHO recommends ≤ 40 dB in residential areas for undisturbed sleep.",
  'Belastung': "German for 'burden' or 'stress'. Used in environmental mapping to grade exposure. Bands: keine (none), geringe (low), mäßige (moderate), starke (strong), extreme (extreme).",
  'PET': "Physiological Equivalent Temperature — a heat-stress metric that combines air temperature, humidity, wind, and solar radiation. Used to grade a block's summertime bioclimate.",
  '§47d BImSchG': "Section 47d of the German Federal Immission Control Act (Bundes-Immissionsschutzgesetz). Requires municipalities to designate 'quiet zones' meant to protect recreation areas from noise.",
  'BImSchG': "Bundes-Immissionsschutzgesetz — Germany's Federal Immission Control Act. The law that regulates emissions, noise, and other environmental pollutants.",
  'Anmeldung': "Mandatory address registration for anyone living in Germany. Must be done at a Kundenzentrum within 14 days of moving. Required for opening a bank account, getting a health card, and most basic services.",
  'Aufenthaltstitel': "German residence permit — the visa document that lets non-EU citizens live and work in Germany. Requires Anmeldung, health insurance, and (for many types) B1-level German.",
  'Einbürgerung': "German naturalization — the process of becoming a German citizen. Usually requires 5–8 years of residence, B1 German, financial self-sufficiency, and passing a civics test.",
  'Sprachschule': "German language school — private course provider. Most offer A1–C2 courses, often intensive (20 hrs/week) for students on a language visa.",
  'Volkshochschule': "Adult education centre (VHS) — one per Bezirk. The cheapest German-course option in Hamburg. Also offers cooking, art, and civics classes.",
  'Bücherhallen': "Bücherhallen Hamburg — Hamburg's public library network. A single annual card gives access to 32+ branches across the city. Not to be confused with Berlin's VÖBB.",
  'Bibliothek': "German for library. Hamburg's public library network is called Bücherhallen Hamburg.",
  'Packstation': "DHL's parcel-locker network — where packages get delivered when you're not home. Uses a PIN or app to open. Named 'Packstation' (yes, that's the actual German name).",
  'Deutsche Post': "Germany's national postal service. Runs Packstation and has staffed post branches (Postfilialen) at many corner shops.",
  'Weihnachtsmarkt': "Christmas market — outdoor stalls selling handcrafts, food, and Glühwein, open in the four weeks of Advent (late Nov to 23 or 24 Dec). Hamburg hosts markets at the Rathausmarkt, Jungfernstieg, and Altstadt.",
  'Adventsmarkt': "Advent market — smaller church-yard or courtyard variant of a Weihnachtsmarkt, usually only open on one or two weekends of Advent.",
  'Wintermarkt': "Winter market — variant of a Weihnachtsmarkt that runs past 24 Dec, often into January. Same style of stalls without the explicit Christmas framing.",
  'Glühwein': "Mulled wine — red or white wine heated with cinnamon, cloves, orange peel and sugar. The signature drink of any Weihnachtsmarkt.",
  'Advent': "The four-week season before Christmas in the German liturgical calendar (four Sundays before 25 Dec). Weihnachtsmärkte open at the start of Advent and close on 23 or 24 Dec.",
  'Kundenzentrum': "Hamburg's citizens' service office — equivalent to Berlin's Bürgeramt. Where you go for Anmeldung, passport renewal, and other civic services. Hamburg has 18 Kundenzentren across 7 Bezirke.",
  'Stadtteil': "Hamburg's neighbourhood unit — roughly equivalent to Berlin's Ortsteil. Hamburg has ~109 Stadtteile. Used colloquially and in official statistics.",
  'Statistisches Gebiet': "Hamburg's smallest official statistical unit, ~2,200 residents each. Sozialmonitoring scores are reported at this level. Finer-grained than a Stadtteil.",
  'Sozialmonitoring': "Hamburg's yearly neighbourhood report card — measures income, jobs, education, and family stability at the ~2,200-resident block level. Combines a current-state snapshot ('Status') with a trend-over-time signal ('Dynamik'). Published by the city's Housing & Urban Development Authority (BSW).",
  'Aufmerksamkeitsgebiet': "City-support tag. A neighbourhood block the Hamburg government has picked for extra investment — either weak now, trending down, or both. Shown in the app as 'City focus area'.",
  'Bezirk': "One of Hamburg's 7 official boroughs (Altona, Bergedorf, Eimsbüttel, Hamburg-Mitte, Hamburg-Nord, Harburg, Wandsbek). Each administered by its own Bezirksamt.",
  'Bewohnerparkgebiet': "Hamburg's resident-parking polygon — a designated zone where Bewohnerparken rules apply. The Hamburg Open Data WFS layer provides polygon boundaries without fee or enforcement hours.",
  'Bewohnerparkausweis': "Hamburg's annual residents' parking permit — applied for at the local Bezirksamt with proof of Anmeldung. Valid within one Bewohnerparkgebiet only. Required if you own a car and live inside a resident-parking area.",
};

// Tile → glossary keys. Only add words that actually surface in that tile's
// caveat / explanation / sources / dataset name. Empty list = no glossary
// section rendered for that tile.
export const TILE_GLOSSARY_KEYS = {
  // Newcomer lens
  rail_transit:                ['S-Bahn', 'U-Bahn', 'HVV', 'Hamburg-Hauptbahnhof'],
  ferry_transit:               ['HADAG', 'HVV'],
  bus_transit:                 ['HVV'],
  intl_food:                   [],
  coworking:                   [],
  english_clinic:              [],
  language_school:             ['Sprachschule', 'Volkshochschule', 'Aufenthaltstitel', 'Einbürgerung'],
  library:                     ['Bücherhallen', 'Bezirk'],
  packstation:                 ['Packstation', 'Deutsche Post'],
  parkzone:                    ['Bewohnerparkgebiet', 'Bewohnerparkausweis', 'Bezirk'],
  nightlife_density:           [],
  sozialmonitoring_status:     ['Sozialmonitoring', 'Statistisches Gebiet', 'Stadtteil'],
  sozialmonitoring_gesamt:     ['Sozialmonitoring', 'Aufmerksamkeitsgebiet'],
  // Commuter lens
  commuter_rail_transit:       ['S-Bahn', 'U-Bahn', 'HVV'],
  commuter_bus_transit:        [],
  commuter_ferry_transit:      ['HADAG', 'HVV'],
  regional_rail_reach:         ['Regionalbahn', 'HVV'],
  cycling_network:             [],
  car_sharing_reach:           [],
  ev_charging_reach:           [],
  airport_reach:               ['S-Bahn', 'Regionalbahn'],
  sozialmonitoring_status_commuter: ['Sozialmonitoring', 'Statistisches Gebiet', 'Stadtteil'],
  sozialmonitoring_gesamt_commuter: ['Sozialmonitoring', 'Aufmerksamkeitsgebiet'],
  // parkzone is shared between Newcomer and Commuter lenses —
  // TILE_GLOSSARY_KEYS is looked up by tile key, not by lens.
};

// -- Spec D: map-pin colour per tier --------------------------------
export const TIER_PIN_COLORS = {
  green:   '#22C55E',   // matches --success
  amber:   '#F59E0B',   // matches --amber
  red:     '#EF4444',   // matches --danger
  unknown: '#9CA3AF',
};

// Hamburg ships ONLY Newcomer + Commuter lenses on day-1 (spec Q9).
// Young Family and Quiet Living are not included in the Hamburg release.
export const LIFE_MODE_LENSES = [
  {slug: 'newcomer', label: 'Newcomer',
   icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="3.5"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/><path d="M17 4l3 3-3 3"/><path d="M14 7h6"/></svg>'},
  {slug: 'commuter', label: 'Commuter',
   icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 12h14"/><circle cx="9" cy="15" r="1"/><circle cx="15" cy="15" r="1"/><path d="M8 21l-2 2M16 21l2 2"/></svg>'},
];

// -- Card drag-reorder key ------------------------------------------
export const CARD_ORDER_KEY = 'addrlens.cardOrder.v1';

// -- Connectivity tile meta ------------------------------------------
export const CONN_META = {
  sbahn:         {label:'S-Bahn',        note:'HVV rapid transit'},
  ubahn:         {label:'U-Bahn',        note:'HHA subway'},
  ferry:         {label:'Ferry',         note:'HADAG pier'},
  regional_rail: {label:'Regional rail', note:'RE / RB — DB Regio'},
  bus:           {label:'Bus',           note:'HVV bus stop'},
  airport:       {label:'Airport',       note:'HAM international'},
};

// -- Compare board ---------------------------------------------------
export const COMPARE_KEY='hamburg-lens-compare-v1'; export const COMPARE_MAX=5;

// -- Title-case small-word set --------------------------------------
export const _TITLE_SMALL = new Set([
  'a','an','the','and','but','or','nor','for','so','yet',
  'at','by','in','of','on','to','up','as','per','via','with','from','into','over','than'
]);

// -- Lens AI panel constants -----------------------------------------
export const _LENS_WITH_AI = new Set(['newcomer', 'commuter']);

export const _ICON_DOWNLOAD = '<svg viewBox="0 0 256 256" aria-hidden="true"><path d="M216,144v64a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8V144a8,8,0,0,1,8-8H88l40,40,40-40h40A8,8,0,0,1,216,144Z" opacity="0.2"/><path d="M216,144v64a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8V144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><polyline points="88 112 128 152 168 112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="40" x2="128" y2="152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>';
