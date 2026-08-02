# Phase 0 — Agency Outreach Kit

**Goal:** get **3 verbal commitments** at **€150/month on a demo** from Berlin relocation agencies.
**Gate:** if fewer than 3 commit, do not build the consumer version.
**Time budget:** 2–3 weeks, ~4 hrs/week.

---

## The list — 10 agencies to contact

Berlin has roughly 40–70 relocation agencies. Start with these ten. Six are large and established; four are smaller, likely faster to pilot with.

| # | Agency | Angle | Contact starting point |
|---|---|---|---|
| 1 | Archer Relocation | Publishes a public family checklist for Berlin — clearly thinks about the same problem | archer-relocation.com |
| 2 | Relokate | HR-facing, positions for corporate mobility | relokatehr.com |
| 3 | FARAWAYHOME | Content-heavy expat brand, publishes district guides | farawayhome.com |
| 4 | Berlin Perfect | Family-focused Berlin relocation | berlinperfect.com |
| 5 | Berlin Nesting | Focus on family homes; published Mietspiegel primer | berlinnesting.com |
| 6 | Crown Relocations Berlin | Global brand, local family desks | crownworldmobility.com |
| 7 | Santa Fe Relocation Berlin | Global brand, corporate volume | santaferelo.com |
| 8 | Sirva Berlin | Global brand, corporate volume | sirva.com |
| 9 | Berlin Relocation Services (BRS) | Independent, mid-size | berlin-relocation.de |
| 10 | Localyze / Envoy (immigration adjacencies) | Immigration-first; family-add-on is exactly your upsell | localyze.com, envoyglobal.com |

Sanity-check the list before dialling — cross-reference on [`farawayhome.com/en/berlin/relocation-agencies`](https://www.farawayhome.com/en/berlin/relocation-agencies) which maintains an active roster.

---

## Sequencing: LinkedIn → Email → Call, in that order

You will get more replies from a LinkedIn message to the *owner or head of family services* than from a cold call to reception. Sequence per agency:

1. **Day 0** — LinkedIn: connection request + short message
2. **Day 3** — Cold email if no LinkedIn reply
3. **Day 7** — One phone call, only if warm

Do not call ten agencies. Send twenty LinkedIn messages and let self-selection do the work.

---

## LinkedIn message (opening — 300 chars max)

Keep it short, name the pain, offer 10 minutes, no attachments.

> Hi [First name] — I'm building an English-language address decision tool for expat families arriving in Berlin (assigned school, catchment, noise, commute, real move-in cost, all in one dashboard). Would 10 minutes next week be worth it to see the prototype and tell me if it saves your team hours? — Sapta

**Do not:** attach a deck, name a price, or use the word "founder."
**Do:** send from a real profile with a real face.

---

## Cold email (Day 3 — 6-line format)

Subject: *English address checker for expat families — worth 10 min?*

> Hi [First name],
>
> Your team currently spends hours reconciling catchment schools, Kita density and dual-commute isochrones by hand for every incoming family. I'm building a tool that does that in ten seconds from an address alone — English, address in, dashboard out, no scraping of listings, all open Berlin Senate data.
>
> Two questions before I invest more:
> 1. Would a per-seat licence at €150/month save one of your consultants an hour per relocation?
> 2. If yes, would you be willing to pilot it for a month at that price when the beta ships?
>
> Happy to send a 90-second Loom or give you 10 minutes live — whichever costs you less time.
>
> — Sapta [signature: role, phone, city, one link to a landing page]

**Rule:** two questions per email, both answerable yes/no. Anything else is friction.

---

## Discovery call script — 15 minutes

**Minute 0–2 — Set the frame.** "Thanks for the time. I'm validating whether this is worth building, not selling anything. Five questions, then I'll show you what I have and you tell me if it's a real product or a fantasy."

**Minute 2–8 — Discovery. Ask, don't pitch.**
1. "Walk me through the last family relocation you did. Where does the time actually go?"
2. "When a family sends you a shortlist of flats, what do you research about each address?"
3. "What do you tell them about the school assignment, and how do you find it?"
4. "What's the single most common question expat families ask you that you can't answer in one click today?"
5. "If a tool gave you all of this from an address alone, in English, in ten seconds, what would that be worth per seat per month?"

**Take dictation. Do not correct them.** Their words are your marketing copy.

**Minute 8–13 — Show the prototype.** Even if it's a Notion page or a spreadsheet with 5 addresses hand-enriched. Show one address → school assignment (you now have this working from `catchment_check.py`), one dashboard sketch, one comparison-board mock.

**Minute 13–15 — The ask.**
> "Here's what I need from you: an honest yes/no. When the beta ships in ~10 weeks, would your agency pay €150/month for one seat? Not signing anything today — I just need to know whether to build it."

**Log the exact response. Verbatim.** Not your paraphrase.

---

## The tracker (copy-paste into a spreadsheet or Notion)

| Agency | Contact person | LinkedIn sent | Email sent | Call date | Response verbatim | Commit? (Yes/No/Maybe) | Follow-up date | Notes |
|---|---|---|---|---|---|---|---|---|
| Archer | | | | | | | | |
| Relokate | | | | | | | | |
| FARAWAYHOME | | | | | | | | |
| Berlin Perfect | | | | | | | | |
| Berlin Nesting | | | | | | | | |
| Crown | | | | | | | | |
| Santa Fe | | | | | | | | |
| Sirva | | | | | | | | |
| BRS | | | | | | | | |
| Localyze | | | | | | | | |

---

## What counts as a "yes"

A **yes** is a named person saying, on record (email or call notes), that their agency **would pay €150/month for one seat when the beta ships**. Anything softer is a maybe.

A **maybe** ("looks interesting, send me updates") is a **no** for gate purposes. The whole point of Phase 0 is to expose the honest picture; you cannot lie to yourself here without paying for it later in the P&L.

## Interpretation of the result

| Yes count out of 10 | What it means | What to do |
|---|---|---|
| **0–2** | The consumer version won't save you. Distribution risk is real. | Do not build. Either find a Berlin-based co-founder with the network, or pick a different problem. |
| **3–5** | The doc's Phase 0 gate is met. | Build Phase 1 MVP as scoped. Ship in 8–12 weeks. Convert the yeses to design partners. |
| **6+** | Pull the timeline forward. | Consider skipping the free consumer tier and going straight to a paid B2B beta with the 6 yeses. |

## Common objections and honest answers

- **"We already have a Berlin school database."** → "You have a list. I'm building the address→school reverse-lookup with catchment polygons, which nobody has done in English. Want to see it work on your last three client addresses?"
- **"Our clients want listings, not analysis."** → "That's exactly why I don't scrape listings — you send me a listing URL, I extract only the address and hand the family a dashboard. You keep the listing relationship."
- **"How is this different from navigator.berlin?"** → "Navigator is German civic tech with no family lens, no catchment school, no real cost, no commute. I'm the family-decision layer that isn't public infrastructure."
- **"Can it be white-labelled?"** → "Yes — Phase 4 in the roadmap. If you're serious we can talk about being one of the first two agencies to co-brand it."

## Timeline

- **Week 1:** 20 LinkedIn messages, hand-picked contacts (heads of family services or founders)
- **Week 2:** cold-email follow-ups for non-responders + first 3–5 calls
- **Week 3:** remaining calls; tally the yeses; write a one-page memo to yourself with the decision

**Do not start MVP code until the memo is written.**
