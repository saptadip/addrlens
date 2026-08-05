# Data source ideas — Berlin Open Data survey

Living reference of Berlin Open Data WFS endpoints not yet used by the app,
plus insights we could derive from data we already fetch. Result of a catalog
scan run on 2026-08-05.

**Already integrated** (for context, don't re-add):

- `adressen_berlin` — address geocoder
- `schulen` — schools + Einschulbereich catchment polygons
- `kita` — registered Kitas with Träger / capacity / approach
- `gruenanlagen` — parks (`gruenanlagen`) + playgrounds (`spielplaetze`)
- `ua_stratlaerm_2022` — 2022 façade-level strategic noise map
- `krankenhaeuser` — hospitals (plan + weitere), nearest within 2 km in Amenities
- `trinkwasserbrunnen` — BWB public drinking fountains, within 800 m in Amenities
- OpenStreetMap supplements — pharmacies, supermarkets, GPs, transit stops,
  plus playground / park gap-fill

Everything below is candidate material.

---

## A. Berlin Open Data datasets worth adding

| # | Dataset (WFS name) | Family-relevance | Notes |
|---|---|---|---|
| 2 | **Luftbelastung im Straßenraum 2015 und 2020** (`ua_luftbelastung_verkehr_2015_2020`) | Traffic-related NO₂ / PM10 / PM2.5 at street level. The health story missing from noise-only. | Same shape as the façade noise layer — per-street pollution scores. |
| 3 | **Berliner Luftgütemessnetz** (`ua_luftguetemessnetz`) | Nearest official air-quality station (live-ish readings). | Sparse network (~15 stations city-wide) → "nearest station: 1.2 km" style card, not per-address. |
| 5 | **Standorte öffentlicher Sportanlagen** (`sportstandorte`) | Public pools, gyms, sports halls, football pitches. | Mentioned in product doc §6 second-wave, still unused. |
| 6 | **Fluglärmschutzbereich BER** (`fluglaermschutz`) | BER aircraft noise zone (SE Berlin). Hard filter for a few Bezirke. | Product doc §6 second-wave. Polygon overlay. |
| 7 | **Umweltzone** (`umweltzone`) | Low-emission zone — matters if the family drives (must have green sticker). | Single polygon, boolean flag per address. |
| 8 | **Verkehrsmengen DTVw 2023** (`verkehrsmengen_2023`) | Daily car counts per major road segment. | Complements noise: "why is this street loud → 20k cars/day". |
| 9 | **Radverkehrsanlagen** + **Radverkehrsnetz** + **Fahrradstraßen** (`radverkehrsanlagen`, `radverkehrsnetz`, `fahrradstrassen`) | Nearby bike lanes, dedicated bike streets, city bike network. | For families biking with kids — is the school run cyclable? |
| 10 | **Fahrradreparaturstationen** (`fahrradreparatur`) | Public bike-repair stations. | Points. Amenity add. |
| 11 | **Badegewässerqualität** (`badegewaesser`) | Bathing-water quality at Berlin lakes / rivers (Wannsee, Müggelsee, …). | Nearest-bathing-spot within 5–10 km. Seasonal but delightful. |
| 12 | **Baumbestand Berlin** (`baumbestand`) | Every street tree — species, age, canopy. | Density around the address = shade + summer heat comfort. |
| 13 | **Planbare Ereignisse im öffentlichen Straßenland** (`planb_ereignisse`) | Scheduled roadworks / closures on the address's street. | Real-time nuisance signal. Time-bounded. |
| 14 | **Stadtstruktur** (`ua_stadtstruktur`) | Urban structure type per block (Altbau, Neubau, Plattenbau, industrial …). | Answers "what kind of building era is this street" — helpful because Altbau + no lift is a real stroller factor. |
| 15 | **StEP Klima 2.0: Klimaszenarien** (`step_klima`) | Heat-island / climate scenarios per neighborhood. | "How hot will this flat be in a summer heatwave?" — climate-forward differentiator. |
| 16 | **Aufgrabeverbote** (`aufgrabeverbote`) | Streets closed to digging — proxy for "recently repaved, no imminent disruption". | Low-signal alone but a nice tidbit. |
| 17 | **Verkehrsunfallsituation Berlin** (tabular, not WFS) | Traffic-accident casualties per road / intersection. | Product doc §6 second-wave. School-run road-safety indicator. |
| 18 | **Gesundheits- und Sozialstrukturatlas GESIx 2022** (`gssa_gesix2022`) | Neighborhood health-and-social index. | ⚠️ Product doc §6 flags ethical / social-profiling risk. Handle with care or omit. |
| 19 | **Monitoring Soziale Stadtentwicklung 2025** (`mss_2025`) | LOR-level socio-economic status index. | Same caveat as #18. |

## B. Derived insights from data we already have

| # | Insight | How | Value |
|---|---|---|---|
| 20 | **Noise percentile for this street** | Rank the façade point's L_DEN against all façade points in the same LOR / district. | "This address is quieter than 78 % of Pankow" reads better than a raw dB number. |
| 21 | **Neighborhood-average vs address noise** | Sample the 20 nearest façade points, compare their mean to the address's L_DEN. | "This flat is 6 dB quieter than the block average" — surfaces courtyard flats. |
| 22 | **Green-cover ratio within 5 min walk** | Sum Grünanlagen polygon area intersected with a 400 m buffer around the address. Divide by buffer area. | Single number (e.g., "12 % green cover") — comparable across addresses. |
| 23 | **Playground diversity / age fit** | Aggregate OSM `min_age`/`max_age` on nearby playgrounds; report age brackets covered. | "3 playgrounds cover ages 1–5, none for 6+" — hyper-family signal. |
| 24 | **Amenity diversity (Shannon index)** | Compute Shannon entropy of the 6 amenity categories within 800 m. | High score = truly walkable mixed-use neighborhood; low = residential-only. |
| 25 | **Kita match score** | Filter kitas by `t_art` (freie / Eigenbetrieb), `ang_1` (Situationsansatz vs Reggio vs Waldorf …), sort by distance. | Families with a strong pedagogy preference get a shortlist, not just a count. |
| 26 | **Kita language flag** | Regex Kita names for language markers ("bilingual", "français", "italiano", "русский", "español" …). | Complements SESB (which only covers Grundschulen). Many private Kitas advertise a second language in the name. |
| 27 | **Catchment school "compactness"** | Compute the catchment polygon's area vs perimeter. Small compact polygons = short walk. Big stretched polygons = wide street network. | Proxy for how far you might have to walk within the catchment. |
| 28 | **Nearest 3 international schools (not just 1)** | We already have all schools with an "intl" keyword filter. Return top-3 instead of 1. | Families often compare 2–3 options. |
| 29 | **School-run walkability** | Along the straight line from address to catchment school, count how many façade-noise points > 70 dB or busy streets crossed. | "Loud route to school" flag. |
| 30 | **Transit connectivity score** | Count unique VBB lines reachable within 800 m walk (from OSM transit stop `network` + `route_ref` tags). | Better than "17 stops" — captures redundancy. |

---

*How to use this file:* when picking the next feature, name the row number
(e.g. "let's do #1 and #17") and the implementation can start from the WFS
endpoint or the derivation recipe listed. Add new rows as new datasets or
ideas surface. Move completed rows into the "Already integrated" block at
the top so this stays a live shortlist.
