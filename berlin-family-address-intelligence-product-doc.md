# Berlin Family Address Intelligence
### Product Concept, Data Architecture & Roadmap

**Version:** 1.0
**Date:** 30 July 2026
**Status:** Pre-validation concept document

---

## 1. One-line concept

> A family enters an apartment address. We return everything that address means for their children — which school it assigns them to, how loud the street is, how far both parents' commutes are, what it will actually cost to move in — using only open public data.

We never hold, host, resell or redisplay apartment listings. We are a **decision layer over a location**, not a portal.

---

## 2. The problem

Expat families arriving in Berlin make a five-figure, multi-year decision on the basis of five photos and a fifteen-minute viewing. The information that actually determines whether the flat works for their family is:

- **Not on the listing** — school catchment, noise level, Kita density
- **Not in a language they read** — German administrative prose, district PDFs
- **Not discoverable** — spread across twelve district school offices, a state geoportal, and a transit authority
- **Discovered too late** — usually after signing

Existing portals compete on inventory and speed of alerts. Nobody competes on *comprehension*. A German family solves this through local knowledge. An expat family has none.

**Target user:** dual-income expat household, 1–3 children under 12, relocating to Berlin, 6–12 weeks of search time, high willingness to pay, near-zero local network.

---

## 3. Architectural principle: address in, insights out

This is the single most important design decision in the document. Everything else follows from it.

**Input:** a street address (`Prenzlauer Allee 42, 10405 Berlin`).

**Output:** a family dashboard about that *location*.

**What we never do:**
- Store, cache, index or redisplay listing content
- Scrape any portal, directly or through a third party (including Telegram bots)
- Operate as a listing search engine

### Why this matters

| Benefit | Explanation |
|---|---|
| **Legal safety** | No exposure to the EU/German database right (§§87a–e UrhG), portal ToS breach, UWG unfair-competition claims, or §202a StGB |
| **Acquirability** | Scout24 will never buy a product built on scraping Scout24. A complement is acquirable; a parasite is litigable |
| **Zero cold-start** | No supply-side chicken-and-egg. Useful on day one with one user and zero listings |
| **Light GDPR footprint** | Nothing personal is required to produce the core output |
| **Speed to launch** | Buildable in weeks, not quarters, by a two-person team |

---

## 4. The three feature pillars

### Pillar 1 — School and Kita reality

The flagship. This is the reason the product exists and the only genuinely defensible moat.

| Feature | Detail |
|---|---|
| **Assigned catchment school** | Berlin allocates primary school by *Einschulungsbereich*. The flat determines the school. Most expat parents don't know this until after signing. We name the school for that exact address |
| **SESB bilingual flag** | Staatliche Europa-Schule Berlin strands exist at only ~20 schools. This is the single most-searched attribute by expat parents. Flag it prominently |
| **School profile summary** | Type, public/private, languages taught, special programmes — in English |
| **Kita density ring** | Count of publicly funded Kitas within a 10-minute stroller walk, drawn as distance rings on the map |
| **International / private school distance** | Many families are contractually or financially tied to one specific school. Show door-to-door distance and transit time |

**The hard part (and therefore the moat):** the official Senate address search returns the *nearest* school, which districts explicitly warn may differ from the responsible catchment school. Several districts state that only their own address directory is binding, and boundaries are redrawn annually. Reconciling twelve districts' street directories into one authoritative, current, English-language lookup is unglamorous manual data work — which is exactly why no funded competitor has done it.

---

### Pillar 2 — Eligibility and true cost

Expat families get silently filtered out of applications: no SCHUFA history, one income supporting four people, a visa that isn't permanent. Months are wasted on flats they were never going to get.

The user fills a household profile **once** (optional, anonymous, session-only by default): income, employment type, number and ages of children, visa status, pets, SCHUFA yes/no.

| Feature | Detail |
|---|---|
| **Income-to-rent traffic light** | 🟢 / 🟡 / 🔴 against the multiple landlords in that segment typically expect |
| **Total cash required on day one** | Displayed in the **same font size as the rent**. Deposit (up to 3× cold rent) + first month + kitchen *Ablöse*. This figure blindsides every newcomer and no portal shows it |
| **Rent fairness check** | Compare asking rent against the Berliner Mietspiegel for that address band. Tells the family whether the price is legally defensible |
| **Lease type badge** | *unbefristet* / *befristet* / Zwischenmiete. Families need unlimited leases for stability, Kita vouchers and school registration — and it's usually buried in German prose |
| **Anmeldung possible: yes/no** | Without registration there is no Kita voucher, no bank account, no residence permit. Binary, critical, invisible on listings |
| **Realism score** | "Will they even reply to us?" — an honest probability estimate so families spend effort where it can work |

---

### Pillar 3 — Daily-life logistics

Families don't optimise one commute. They optimise a daily loop.

| Feature | Detail |
|---|---|
| **Dual-commute intersection** | Both partners enter their workplace. Draw both transit isochrones and show whether this address sits in the overlap. Simple to build on GTFS, immediately legible, and highly screenshot-shareable — which is how it spreads |
| **Stroller score** | Floor number × lift present (a 4th-floor Altbau with no lift is a hard no with a toddler), Kinderwagenraum, ground-floor access |
| **Street noise** | Façade-level L-DEN and L-N readings from the strategic noise maps. The façade layer gives a per-building number, not a street-level guess. A quiet-street indicator is something every parent wants and no portal offers |
| **Playground proximity** | Nearest public playground, walking distance along the actual street network — not crow-flies radius |
| **School-run road safety** | Aggregate accident data (causes, road-user type, severity) into a walking-route safety indicator. Nobody does this and parents would care a great deal |
| **Green and sport access** | Nearest parks, public sports facilities, swimming |
| **Daily essentials** | Supermarket, pharmacy, GP, paediatrician within walking distance |

---

## 5. Cross-cutting product features

These emerged during discussion and must not be dropped.

### 5.1 The comparison board — *this is the product*

A single lookup is a demo. A family is deciding between four flats. Let them save **3–5 addresses into a side-by-side grid**:

| | Address A | Address B | Address C |
|---|---|---|---|
| Catchment school | | | |
| SESB bilingual | | | |
| Kitas within 10 min | | | |
| Night noise (L-N) | | | |
| Dual-commute overlap | | | |
| Stroller score | | | |
| Total move-in cash | | | |
| Rent vs Mietspiegel | | | |

This is the moment of willingness-to-pay, and the artefact they forward to their partner.

### 5.2 Freemium boundary

- **Free:** unlimited single-address lookups. This is the marketing. It costs almost nothing to serve and it is the thing people share.
- **Paid:** the comparison board, PDF export, dual-commute isochrone, saved history, household eligibility profile.

The free thing spreads. The paid thing is the thing they need.

### 5.3 Anonymous by default

A Berlin address plus household income plus children's ages is a GDPR-relevant profile. Design accordingly:

- No login required for a lookup
- Session-only storage by default
- Login only if the user wants to persist a comparison
- Clear deletion path, minimal retention

This is both a compliance decision and a trust signal for a market that cares about exactly this.

### 5.4 Visible provenance on every panel

Every data panel carries its source and vintage — e.g. *"Einschulungsbereich · Geoportal Berlin · Schuljahr 2026/27"*. Catchments shift, noise maps are periodic snapshots.

This does three jobs at once: it satisfies the dl-de/by-2.0 attribution requirement, it manages user expectations honestly, and it is the single strongest credibility signal available to an unknown product making consequential claims.

### 5.5 English first

All output in English, with German administrative terms retained in parentheses so users can use them at the Bürgeramt. This is a feature, not a translation task.

### 5.6 Interpretive AI layer — on-infrastructure, never third-party

From Phase 3 on, the app carries a small locally-hosted LLM (baseline: Qwen2.5-1.5B-Instruct, 4-bit) that turns the numeric data the rules engine already produced into short prose in the app's voice. Strategic reasons:

- The target audience is English-speaking expat families landing in a German administrative system. Their #1 pain point is *interpretation* — what "freier Träger" means, what an Einschulbereich implies for enrolment, how SESB really works — not data lookup. This is the friction a language model reduces natively and a rules engine cannot.
- The interpretive layer sits **on top of** the rules engine, never as a substitute for it. Every prompt is grounded in facts the deterministic pipeline already computed. The LLM's job is prose over those facts; it never generates data. This bounds hallucination cost.
- Inference runs on infrastructure we control (own hardware or an EU-based node). **No third-party AI provider is involved.** This preserves the app's data-minimisation posture (see §5.3 and §7 GDPR row) and matches the "open data only, no scraping" ethos — the AI story stays consistent with the data story.
- Deployment shape is a **shared inference service** (see `microservice-refactor-plan.md` §7): one inference cluster serves every city instance over HTTP; the model is never baked into per-city app images.

Scope discipline: every LLM-backed feature must answer *"what would this look like without the LLM, and is that acceptable?"* If a templated version is 80% as good, the templated version ships. The LLM is reserved for the 20% where synthesis, translation, or narrative earns its keep. Concrete first candidates: kita / SESB / bureaucracy translator (§5.5 extended), comparison-board verdict (§5.1), and a per-address impression summary based on user votes.

---

## 6. Data sources — all open, all commercially usable

Primary portal: **daten.berlin.de**, licence *Datenlizenz Deutschland – Namensnennung 2.0* (dl-de/by-2.0). Attribution mandatory.

### Core — build these first

| Dataset | Format | Purpose | Notes |
|---|---|---|---|
| **Adressen Berlin** | WFS | Foundation: validates every input, free geocoding | Official address points with coordinates from the surveying offices; refreshed monthly, deviations possible |
| **Schulen** | WFS | School locations, type, public/private, **and Einschulbereiche for the current school year** | Main locations only — verify multi-campus schools manually. Set by the twelve district school offices, consolidated by Amt für Statistik Berlin-Brandenburg |
| **Kindertagesstätten** | WFS | Kita density rings | Publicly funded Kitas with attributes. **Does not include live availability** — that gap remains unfilled by anyone |
| **VBB-Fahrplandaten (GTFS)** | GTFS ZIP | Dual-commute isochrones | Updated twice weekly (Wed/Fri). Licence **CC-BY**, attribution string: *"VBB Verkehrsverbund Berlin-Brandenburg GmbH"*. Logos provided. GTFS-RT realtime feed exists — **skip it**, unnecessary here |
| **Strategische Lärmkarten** | WFS | Noise indicator | L-DEN and L-N per source, plus **façade-level readings for noise-affected residential buildings** — use the façade layer |

### Second wave — differentiators

| Dataset | Format | Purpose | Notes |
|---|---|---|---|
| **Grünanlagenbestand incl. Spielplätze** | WFS | Playground and park proximity | **Caveat:** excludes green space at schools, Kitas, cemeteries, allotments and sports grounds — will undercount playgrounds. Supplement with OSM |
| **Standorte öffentlicher Sportanlagen** | WFS | Swimming, clubs, sport | Public core facilities on state-owned land |
| **Detailnetz Berlin** | WFS | Walking distances along real paths, not radii | Essential for credible "10-minute walk" claims |
| **Verkehrsunfallsituation Berlin** | Tabular | School-run road safety indicator | Causes, road-user type, severity |
| **Fluglärmschutzbereich BER** | WFS | Aircraft noise zones | Narrow relevance; hard filter in the southeast |

### External sources

| Source | Licence | Purpose | Warning |
|---|---|---|---|
| **OpenStreetMap** | ODbL | Pharmacies, GPs, paediatricians, supermarkets, playgrounds the city dataset misses | **Share-alike.** Keep OSM-derived data architecturally separate from the proprietary layer |
| **Berliner Mietspiegel** | Public | Rent fairness check | Update on each new edition |
| **Amt für Statistik / LOR** | Public | Neighbourhood demographics, share of children | **Handle with care.** Short step from "family-friendly" to social profiling — ethical and reputational risk. Consider omitting entirely |

### Engineering notes

- **Berlin Open Data first, OSM as fallback / supplement.** Where a Berlin geoportal dataset exists (addresses, schools, catchments, Kitas, playgrounds via Grünanlagenbestand, transit via VBB GTFS, noise), use it as the primary source. OSM covers categories the city doesn't publish (pharmacies, GPs, supermarkets) and supplements known undercounts (Grünanlagenbestand excludes school/Kita/sports/cemetery green space).
- **Cache, don't proxy.** WFS endpoints are not built for per-request app traffic. Pull each dataset on a schedule into PostGIS and run your own spatial queries.
- **Refresh cadence:** GTFS weekly · addresses monthly · Kitas quarterly · noise and catchments annually (catchments before each school year).
- **Attribution component** in the footer and per-panel from day one.

---

## 7. Legal and compliance requirements

| Area | Requirement |
|---|---|
| **No scraping — ever** | Not directly, not via a subscribed Telegram bot, not via any intermediary. Receiving scraped data does not transfer liability; it makes you a commercial exploiter of infringing data with no ability to diligence the source |
| **Database right** | §§87a–e UrhG (EU Database Directive). Portals hold a *sui generis* right against systematic extraction of substantial parts. The sharpest tool available to them |
| **Portal ToS** | Contractual breach → injunction plus costs |
| **UWG** | Unfair competition / targeted obstruction |
| **§202a StGB** | Becomes **criminal** where access controls are circumvented, e.g. credentials that aren't yours |
| **GDPR** | Household income, visa status, children's ages = sensitive profile. Anonymous-by-default architecture, lawful basis, deletion path, data minimisation. **AI processing stays on our own infrastructure** — no third-party AI provider (OpenAI, Anthropic, Groq, …). Removes cross-border transfer, sub-processor listing, and DPA-negotiation overhead. Any future change requires a written DPIA (see refactor plan §0 / §7.7) |
| **dl-de/by-2.0** | Exact attribution form *"Geoportal Berlin / [dataset title]"* |
| **VBB CC-BY** | Named attribution required; logos supplied |
| **ODbL** | Share-alike — isolate OSM-derived data |
| **WoVermRG** | Wohnungsvermittlungsgesetz applies if you ever touch brokerage. Stay out of it |
| **Entity & IP** | German UG or GmbH, contractor agreements assigning code ownership, trademark filed, imprint compliance |

---

## 8. Product roadmap

### Phase 0 — Validation (Weeks 1–4) · **Do this before writing production code**

| Task | Why |
|---|---|
| **Verify the Einschulbereiche WFS returns usable catchment polygons**, not just school points with a district code | This single check determines whether the headline feature is possible. One afternoon. **Do it first** |
| Manually build the address→school lookup for **two districts** from their street directories | Proves the data-reconciliation work is tractable at scale |
| Spreadsheet prototype: 10 real addresses, enriched by hand | Costs nothing, tests the output |
| **Call 10 Berlin relocation agencies.** Target: 3 verbal commitments at €150/month on a demo | The real unknown is not "can we build it" but "will anyone pay". If three agencies won't commit, the consumer version won't save you — and you'll have learned it for ₹2 lakh instead of ₹20 |

**Gate:** proceed only if the catchment data is usable **and** at least two agencies express paid interest.

---

### Phase 1 — MVP (Months 2–4)

**Scope: Pillar 1 only, single address, free, no login.**

- Address input + geocoding (Adressen Berlin WFS)
- Assigned catchment school + SESB flag + school profile, in English
- Kita count within 10-minute walk
- Nearest international school
- Map with catchment polygon overlay
- Provenance stamps + attribution footer
- Anonymous, session-only

**Ship criterion:** a family can answer "which school will my child go to if I take this flat?" in under ten seconds. Nothing else.

---

### Phase 2 — Comparison and monetisation (Months 5–8)

- **Comparison board** (3–5 addresses side by side) — **paywalled**
- PDF export — paywalled
- Noise layer (façade-level L-DEN / L-N)
- Stroller score (floor × lift × Kinderwagenraum × playground)
- Playground and green space
- Optional account for saved comparisons
- **Launch consumer pricing as a one-time pass (€49–79), not a subscription** — the pain lasts ~3 months, so a monthly plan guarantees 100% churn

---

### Phase 3 — Eligibility and commute (Months 9–14)

- Household profile (anonymous, optional)
- Income-to-rent traffic light
- **Total cash required on day one**
- Mietspiegel rent fairness check
- Lease type badge + Anmeldung yes/no
- Realism score
- Dual-commute isochrone intersection (VBB GTFS)
- School-run road safety indicator

---

### Phase 4 — B2B (Months 12–24)

- **Agency dashboard**: multi-client, bulk address analysis, white-label PDF — €150–300/month/seat
- **Corporate mobility licence**: annual seat-based, English reporting for HR teams — €6k–20k/year
- **Affiliate integrations**: liability and contents insurance, banking, internet, movers, furnished providers — €30–150 per converted lead, and a family signing a lease converts on 3–4 simultaneously
- **Enrichment API**: sell the layer to portals and proptech — highest leverage, longest sales cycle
- Approach **Scout24 and AVIV partner API programmes** using B2B revenue and logos as leverage

---

### Phase 5 — Expansion (Year 3+)

Replicate the pattern city by city, in order of open-data maturity: Hamburg, Munich, Cologne, Frankfurt. The architecture is city-agnostic; only the data pipeline and the catchment reconciliation are local. Consider Netherlands and Austria thereafter.

---

## 9. Business model

| Stream | Buyer | Price | Notes |
|---|---|---|---|
| Consumer pass | Expat family | €49–79 one-time | Not a subscription. Pain lasts 3 months |
| Agency SaaS | Relocation agencies (~40–70 in Berlin) | €150–300/month | They do this research manually today |
| Corporate licence | Global mobility teams (Zalando, Delivery Hero, N26, SAP, US firms with Berlin offices) | €6k–20k/year | Longest sales cycle, best margin |
| Affiliate / lead-gen | Insurance, banking, internet, movers | €30–150 per lead | The sleeper stream |
| Data API | Portals, proptech | Negotiated | Highest leverage |

**Market size reality check:** Berlin receives roughly 8,000–12,000 expat *family* households per year. That is the ceiling. Realistic capture is low single-digit percent. Plan accordingly.

---

## 10. Financial model (illustrative)

Assumptions: EUR ≈ ₹100 · founder + one developer in Kolkata (the core cost advantage) · Berlin-facing sales.

| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Consumer passes | €2k | €12k | €25k |
| Agency SaaS | €0 | €18k | €42k |
| Corporate licences | €0 | €12k | €45k |
| Affiliate / leads | €1k | €14k | €38k |
| **Revenue** | **€3k** | **€56k** | **€150k** |
| Costs | €16k | €32k | €62k |
| **Net** | **−€13k** | **+€24k** | **+€88k** |

**Cost detail:** one developer (₹5–6L/yr) · infra and geocoding (€2–4k) · GDPR/legal setup and German UG entity (€3–5k one-time) · marketing (€500–1,500/month scaling).

**Cumulative invested:** ~€20k (₹20 lakh)
**Cumulative net by end of Year 3:** ~€99k (₹99 lakh)
**Cash multiple:** ~5× · **IRR:** ~180%

> **Honest discount:** this is the *good* case, at roughly 20–25% probability. Expected value is materially lower. These are illustrative scenarios, not forecasts. Not financial advice.

---

## 11. Exit scenarios

Price is anchored by **build-vs-buy**, not by revenue. Replicating the enrichment layer internally is ~2 engineers × 9–12 months plus data ops — call it **€400k–700k**. Above that, an acquirer simply builds.

| Position at exit | Likely price |
|---|---|
| Working product, no revenue | €50k–200k (asset sale) |
| ~€50k ARR, a few agency contracts | €300k–700k |
| ~€150k ARR + 3–4 corporate logos + clean data moat | €700k–2M |
| Genuine competitive threat, two bidders | €2M–5M |

**What commands a premium** (things they cannot rebuild): signed corporate contracts · exclusive data partnerships · brand among expat families · **a second bidder in the room**.

**What kills the deal outright:** any scraped data in the stack · GDPR sloppiness · messy IP or entity structure.

**Structure reality:** expect 40–60% held back as earnout over 2–3 years contingent on you staying and hitting targets. Headline number ≠ actual number.

**Strategic note:** don't build to sell to ImmoScout. Build to sell to **Scout24, AVIV (Immowelt), or a relocation-services rollup** — and let each know the others exist. A single-buyer negotiation is price-taking. The consolidators and the #2 player are often hungrier for tuck-ins than the market leader.

**Threshold that matters most:** getting to €50k ARR with 2–3 named corporate logos. That is where you stop being an asset sale and start being an acquisition — a far bigger jump in value than going from €50k to €150k ARR.

---

## 12. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Distribution, not product, is the bottleneck** — selling into Berlin from Kolkata with no local network; German B2B proptech runs on introductions | **Highest** | Phase 0 agency calls before any build. Consider a Berlin-based commission partner or advisor with equity |
| Catchment WFS returns points, not usable polygons | High | Verify in week 1. Fallback: manual district-directory reconciliation (which is also the moat) |
| Incumbents ship the same features | High | Compete on the one thing that requires manual bureaucratic labour, not on general scoring |
| Consumer CAC exceeds LTV | High | Never fund growth on B2C. Use it purely as top-of-funnel proof for B2B |
| German legal exposure (GDPR, imprint, WoVermRG) | Medium | Budget real legal advice *before* launch. German UG entity early |
| Catchment data goes stale | Medium | Annual refresh before each school year; visible vintage stamps set expectations |
| Seasonality — search peaks with the school year | Low | Match B2B sales cycle to it |

---

## 13. The single most important next action

**Verify that the Berlin Schulen WFS returns usable Einschulbereich polygons rather than school points with a district code.**

The dataset description mentions both. The difference determines whether the headline feature is buildable directly or requires manual reconciliation of twelve district street directories.

It is one afternoon of work. Nothing else in this document should begin until it is done.

> **Status (2026-08):** cleared. 394 usable Einschulbereich polygons, 87.3% clean 1:1 catchments. Full details in `phase0/wfs-validation-report.md`. Phase 1 (MVP) and Phase 2 (comparison + noise + stroller) shipped against these findings.

---

## 14. Engineering conventions

The codebase in `phase0/`, `phase1/`, `phase2/` is the reference for the pre-LLM shape and style — these directories are frozen as history-as-artefact (§14.1). §14.2–§14.13 below describe that shape and remain the baseline for anything the interpretive AI layer does not touch. **Phase 3 introduces the interpretive AI layer (§5.6) and evolves — but does not replace — those conventions.** The evolved rules are in §14.14; read them alongside §14.2–§14.13 for any Phase 3+ work.

### 14.1 Directory layout

- One directory per phase (`phase0/`, `phase1/`, `phase2/`). Each phase is self-contained and runnable on its own.
- **Preserve older phases untouched.** A new phase copies the previous phase's files and extends additively. Old phases are the reference artefacts and the diff-history for reviewers.
- Product doc + design-system + README stay at repo root.

### 14.2 Server shape (Phases 0–2)

- One `server.py` per phase, ~500–1000 lines, single process.
- **Stdlib only:** `http.server`, `socketserver`, `urllib`, `json`, `threading`, `math`, `unicodedata`, `pathlib`.
- **Only external dep:** `shapely` (`pip3 install --user shapely`). No frameworks (Flask/FastAPI/Django), no ORM, no build step, no bundler, no `requirements.txt` unless a hard need appears.
- Run: `python3 server.py` (port 8000 default; override with `PORT=8001 python3 server.py`).
- Selfcheck: `python3 server.py test` (see §14.8).

**Phase 3 evolves this** — the interpretive AI layer (§5.6) requires an isolated virtualenv and an MLX runtime, so Phase 3's server.py is no longer stdlib-only. See §14.14 for the updated rules that apply from Phase 3 onward. `phase0/`, `phase1/`, `phase2/` remain frozen under the original §14.2 rules as reference artefacts (§14.1).

### 14.3 Frontend shape

- One `index.html` per phase, ~1000–2000 lines, everything inline (CSS + JS + SVG icons).
- Vanilla JS. External libs limited to Leaflet (map) and Plus Jakarta Sans (Google Fonts). No React/Vue/Svelte/htmx.
- No build step. Edit the file, hard-refresh the browser.

### 14.4 Data-sourcing rule (see §6)

- Berlin Open Data first, OSM as fallback / supplement. Every new category answers "primary from BOD? if not, why not?"
- Per-item `source: "bod" | "osm"` tag on every feature so mixed-provenance strings can be built honestly.
- When merging BOD + OSM for the same category, dedupe OSM against BOD centroids (see `_merge_bod_and_osm` in `phase2/server.py`).

### 14.5 Provenance

- Every panel/card in the UI shows source + vintage (§5.4).
- Every API response includes either a top-level `provenance` map (per-domain) or a per-category `provenance` string.
- Mixed sources use the `_mixed_provenance()` pattern from `phase2/server.py` — the string reflects what actually contributed to *this* result, not a static footer.
- Footer attribution mandatory (§Appendix).

### 14.6 Caching strategy

- **Small point layers** (schools, catchments, kitas — thousands of points): load once at startup into `Index.*` attributes, filter in memory.
- **Large / polygon layers** (parks, playgrounds, façade noise — millions of points or polygons city-wide): per-request bbox WFS query, cached in an in-memory dict keyed by rounded `(lon, lat, radius)`.
- Threading locks around every cache dict — the stdlib server is threaded.

### 14.7 API conventions

- `GET /` → HTML. `GET /api/*` → JSON. `GET /health` → `{ok: true, ...}`.
- Response: `{ ...data, provenance: {...} }` on success, `{ error: "..." }` on failure.
- HTTP status: 200 for success, 400 for bad input, 404 for not-found, 502 for upstream failures. Errors always carry a plain-English `error` field.
- **Partial success** in aggregating endpoints (e.g. `/api/amenities`) — per-category `error` field lets one bucket fail without failing the whole call. The frontend can retry (see the auto-retry in `fetchAmenities`).

### 14.8 Testing

- Single `_selfcheck()` function in each `server.py`, invoked with `python3 server.py test`.
- Cover:
  1. Happy path — a known-good Berlin address returns expected school, kitas, catchment.
  2. Rule-based tier transitions (noise thresholds, stroller tiers) — pure functions, no network.
  3. Integration merges — BOD + OSM dedupe, JSON parse safety, error paths.
- Network-dependent assertions gate gracefully: if the WFS is unreachable, print "skipped" rather than fail.
- **No pytest, no fixtures dir, no per-function suites** unless a specific feature genuinely needs one.

### 14.9 Frontend patterns

- Design tokens live in `:root` (`--bg`, `--hero-bg`, `--result-bg`, `--brand`, `--ink`, `--muted`, `--sh-1`, `--sh-2`, ...). Reuse; do not invent new hex values without a token.
- Card shape: `.cell` with a left color bar (`::before`, `scaleY(0) → 1` on hover) and rounded corners.
- Tier colors: **green / amber / orange / red** for 4-tier metrics (noise); **green / amber / red** for 3-tier metrics (stroller). Class the container element `.tier-<name>` and style children via descendant selectors so a single class swap re-colours the whole card.
- Font: Plus Jakarta Sans. Icons: inline SVG strings in one shared `ico = {...}` object.
- **`[hidden]` gotcha (learned twice):** keep `[hidden]{display:none!important}` at the top of the stylesheet. Any element whose class sets `display:` (flex, inline-flex, grid) will otherwise ignore the attribute. Do not remove that rule.

### 14.10 Anonymity & storage (§5.3)

- No login. No cookies. No server-side session.
- User-scoped state lives in `localStorage` only, keyed `berlin-lens-<feature>-v<n>`.
- Any personal input (household profile in Phase 3) must be opt-in and session-only by default. Clear deletion path required.

### 14.11 Ponytail annotations

- Deliberate simplifications with a known ceiling carry a `ponytail:` comment naming the ceiling and the upgrade path. Example from `phase2/server.py`:

  ```python
  # ponytail: centroid + haversine, not nearest-boundary-point. Ceiling: for
  # very large polygons (e.g., Tiergarten) the centroid can be 500m+ from the
  # nearest edge; upgrade path is a projected CRS + shapely.distance.
  ```

- Do **not** strip these — they are the standing debt ledger. Address one when you have a real reason (a bug, a metric, a user complaint), not on a schedule.

### 14.12 Live-browser QA

- After any UI change, drive the flow end-to-end in a real browser (Playwright MCP is fine) covering: **initial-empty state, error state, happy path, and any interactive form**.
- Type checks and the selfcheck verify code correctness — not feature correctness. Do not report a UI ship as done without opening it in a browser.
- Clean up screenshots after the QA session (they are ephemeral).

### 14.13 Commit style

- Short, imperative subject (`git log --oneline` in this repo is the reference).
- Split by concern where the diff supports it (doc-policy vs. code, for example).
- Never commit scraped or listing data. Never commit personal test data with real household details.

### 14.14 Phase 3+ conventions (interpretive AI layer)

Phase 3 introduces a locally-hosted LLM (§5.6) and formally evolves — not deletes — the conventions above. The old rules stayed in force for a reason (minimum surface area, no dep hell, easy to fork, easy to run for years). The new rules preserve that spirit for the parts of the app that don't need the model, and quarantine the ML runtime to the one place that does.

**Evolved rules**

- **Fewest moving parts that serve the feature.** `phase3/server.py` still owns lookup / amenities / noise; the LLM is a strictly additive layer. If a feature can be done with the rules engine alone, it is.
- **LLM used for interpretation over data, never for data generation.** Every prompt is grounded in facts the rules engine has already computed. The LLM writes prose over those facts; it does not invent them. This is the single discipline that keeps hallucination cost bounded.
- **Every prompt cites the rules-engine facts it must respect.** Facts are passed to the model as structured JSON in the prompt context; the model paraphrases, never enriches.
- **No third-party AI provider.** All inference on our own infrastructure (see §5.6, §7 GDPR row).
- **Version-pin the model + runtime.** `requirements.txt` with exact versions. `LLM_MODEL_ID` pinned to a specific HuggingFace revision. Model files cached under `~/.cache/huggingface`; never checked into the repo.
- **Isolated virtualenv.** ML deps (MLX / `mlx-lm` / `transformers`, or `llama-cpp-python` on non-Apple hardware) live in `phase3/venv/` — never installed into the system Python. `phase3/venv/` is `.gitignore`d.
- **Graceful degradation.** LLM endpoint failures (model not loaded, timeout, OOM) return `503` with a plain-English error. The rest of the app is completely unaffected. Never block the map on the LLM.
- **Frontend-side.** No streaming UI for the current baseline model — call, wait ~1–2 s, render the result in one shot. Add streaming only if a real UX complaint surfaces.

**Microservice topology (production shape).** From Phase 3's monolithic server, the LLM later factors out into a **shared inference service** — one inference cluster serving every city instance over HTTP. See `microservice-refactor-plan.md` §7. The model is never baked into per-city app images. Any future ship that proposes doing so must first revisit refactor-plan §7.1.

**Scope test.** Every proposed LLM-backed feature must answer: *"what would this look like without the LLM, and is that acceptable?"* If a templated version is 80% as good, the templated version ships. Reserve the LLM for the 20% where synthesis, translation, or narrative genuinely earns its keep.

---

## Appendix — Attribution requirements

```
Geoportal Berlin / Adressen Berlin
Geoportal Berlin / Schulen
Geoportal Berlin / Kindertagesstätten
Geoportal Berlin / Strategische Lärmkarten
Geoportal Berlin / Grünanlagenbestand Berlin
Geoportal Berlin / Detailnetz Berlin
Datenlizenz Deutschland – Namensnennung 2.0 (dl-de/by-2.0)

VBB Verkehrsverbund Berlin-Brandenburg GmbH (CC-BY)

© OpenStreetMap contributors (ODbL) — kept architecturally separate
```

---

*This document consolidates the concept, feature set, data architecture, legal constraints, roadmap, business model and financial scenarios discussed. Financial and valuation figures are illustrative scenarios for planning purposes, not forecasts or financial advice. Legal points describe the shape of the problem and are not a substitute for advice from a qualified German lawyer.*
