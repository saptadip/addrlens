# Cloudflare WAF setup — addrlens.de

Free-plan edge protection for the app. All rules are configured through the Cloudflare dashboard against the `addrlens.de` zone. This document reflects the Free-plan capabilities as documented at [developers.cloudflare.com/waf](https://developers.cloudflare.com/waf/) and confirmed against the dashboard during initial setup.

The rules complement — they do not replace — the per-IP app-level rate limits enforced by `app/core/rate_limit.py` (10/minute on `/api/history`, 60/minute on `/api/lookup`, 10/minute on `/api/lens_insight`).

## Free-plan quotas — what you get to work with

| Feature | Free-plan quota | Source |
|---|---|---|
| WAF Custom Rules | 5 rules total; all actions except **Log** are available | `developers.cloudflare.com/waf/custom-rules/` |
| WAF Rate Limiting Rules | 1 rule total; **Block only** (Managed Challenge, JS Challenge, Interactive Challenge, Log are all paid-plan features for Rate Limiting) | `developers.cloudflare.com/waf/rate-limiting-rules/` and dashboard verification |
| Rate Limiting expression fields | **Path** and **Verified Bot** only | Same |
| Rate Limiting counting characteristic | **IP address** only | Same |
| Rate Limiting counting period | **10 seconds** only | Same |
| Rate Limiting mitigation timeout | **10 seconds** only | Same |
| Custom Rules expression fields | `http.request.uri.path`, `http.request.method`, `http.user_agent`, `http.referer`, `ip.src`, `ip.geoip.country`, `ip.geoip.asnum`, `cf.client.bot` (Verified Bot boolean), and more standard HTTP fields | CF Custom Rules docs |
| Not available on Free | `cf.bot_management.score` (needs Enterprise + Bot Management add-on) | CF Bot Management docs |

## Where to click in the Cloudflare dashboard

Both rule types now live under the modern **Security rules** page:

1. Cloudflare dashboard → select the zone `addrlens.de`.
2. Sidebar → **Security** → **Security rules**.
3. **Create rule** →
   - **Custom rules** — for WAF Custom Rules.
   - **Rate limiting rules** — for Rate Limiting Rules.

If your dashboard sidebar reorganises again, search for "Security rules" from the top-right search bar in the zone.

## Rate Limiting Rule (1 free — covers both AI endpoints via OR)

The Free plan allows one rule and only `Block` as an action. Both AI-inference endpoints hit Cloudflare Workers AI on cache miss, so both need edge protection — the rule uses an OR condition on the URI path to cover both under the single free-tier slot.

Configuration:

- **Rule name:** `AI endpoints rate limit — 5 in 10s`
- **When incoming requests match:** `(http.request.uri.path eq "/api/history") or (http.request.uri.path eq "/api/lens_insight")`
- **Rate:** 5 requests per 10 seconds
- **With the same characteristics:** IP address
- **Then take action:** Block
- **For a duration of:** 10 seconds

Rationale for the numbers:

- 5 requests per 10 seconds equals a sustained ceiling of ~30 requests per minute per IP. That is 3× the app-level slowapi cap (10/minute on each endpoint), so legitimate browser traffic never trips this edge rule — it exists to catch clients that bypass the app-level limiter (rotating headers, edge-only clients, distributed abuse).
- Because the CF Free plan caps the mitigation timeout at 10 seconds, an offender is automatically released after 10 seconds. A human hitting Refresh backs off and continues; a scripted client that keeps hammering re-trips every 10 seconds and effectively caps at ~30/minute regardless of intent.
- Block returns HTTP 403 at the edge — the request never reaches the origin, so it also does not consume Cloudflare Workers AI neurons or Hetzner CPU.

Endpoint cost profile at a glance:
| Endpoint | LLM tokens per uncached call | Cache TTL | Volume shape |
|---|---|---|---|
| `/api/history` | ~260 max_tokens | 7 days per ~100 m grid | Low — one click per address, cached |
| `/api/lens_insight` | ~1400 max_tokens | 7 days per (lens, ~100 m grid) | 4× per address (one per lens), higher scrape multiplier |

Both under the same rule means an IP burning through addresses via either endpoint hits the same 5-in-10s cap.

## Custom Rules (5 free)

Currently 2 of 5 slots active (Rules 1 and 2). Rules 3-5 are documented but not deployed — see each section for why the slot is empty.

Custom Rules are evaluated in the order shown in the dashboard. Reorder from within the Security rules page after saving.

### Rule 1 — Exempt health probes from all downstream rules

Prevents any future uptime probe from being challenged or blocked. Place this at the **top** of the list.

- **Name:** `health probes — skip WAF`
- **Expression:** `(http.request.uri.path in {"/health" "/ready"})`
- **Action:** **Skip**
- **Skip:** All remaining custom rules, All rate limiting rules

### Rule 2 — Block empty-User-Agent API traffic

Every real browser and every legitimate SDK sends a User-Agent string. An empty or single-character UA on an API endpoint is a 100% scripted signal.

- **Name:** `api — block empty UA`
- **Expression:** `(starts_with(http.request.uri.path, "/api/")) and (len(http.user_agent) lt 5)`
- **Action:** **Block**

### Rule 3 — DISABLED (was: country friction for API endpoints)

Originally this slot held a Managed-Challenge rule against `/api/*` for any IP outside a small EU-plus allowlist (`DE AT CH FR NL PL US GB`). The intent was defense-in-depth against non-target-audience abuse of the LLM-backed endpoints. The intent was wrong for this app, and the implementation broke real users.

**Why disabled (2026-09-10):**

- **Target audience is inherently global.** People evaluating Berlin addresses include incoming expats researching before they move, tourists deciding on neighbourhoods, family abroad checking on new arrivals, journalists, researchers, and every subscriber to any newsletter that mentions the site. An allowlist model is fundamentally wrong for a public open-data portal.
- **False positives silently break the app.** Legitimate visitors on corporate proxies, Cloudflare Warp, iCloud Private Relay, mobile roaming, or VPNs with non-EU exits routinely present a non-DE IP to Cloudflare. Every one of them tripped a Managed Challenge on the first `/api/lookup` call. The challenge returns an HTML captcha page as the response body; the SPA's `fetch().then(r => r.json())` chokes on `<!DOCTYPE` and throws `Unexpected token '<'`. The user sees a red error banner and leaves. This is the general failure mode Rule 4 (below) warns about — Rule 3 was quietly hitting it.
- **What it was actually protecting is already covered elsewhere.** Cloudflare Workers AI cost on `/api/lens_insight` is bounded by the Rate Limiting Rule (5 req/10s per IP) plus a 7-day server-side cache. Berlin Geoportal WFS quota is bounded by server-side caching + the weekly OSM refresh. Rule 3 protected against an abstract "unusual traffic" that never manifested as real abuse.
- **A determined abuser routes through Germany anyway.** Free VPNs with DE exits are 30 seconds away. The rule filtered unlucky legitimate users, not attackers.

**Client-side belt-and-suspenders (also shipped):** `web/static/modules/api.js` exports a `readJson()` helper that verifies `Content-Type: application/json` before parsing. If any upstream network layer — future WAF rule, corporate captive portal, ISP MITM interstitial — serves HTML where the app expects JSON, users see "Your network provider intercepted the request. Please refresh the page and try again — if it keeps happening, try a different network." instead of a stack trace. Symptom containment, not root cause.

The slot is free for a concrete abuse pattern (specific ASN, User-Agent, JA3 fingerprint) once one surfaces in Cloudflare Security → Events.

### Rule 4 — Reserved slot (do NOT use Challenge actions on /api/*)

Originally this slot held a Managed-Challenge rule against an AI-inference endpoint (the since-removed `/api/card_insight`). It broke every real user. The reason is general and worth internalising, not just avoiding a specific rule:

**Managed Challenge, Interactive Challenge, and JS Challenge all work by returning an HTML captcha page.** For a top-level page navigation the browser renders it and the user (or the invisible JS check) solves it. For a `fetch()` / `XHR` call from the SPA — which is how `/api/lens_insight`, `/api/history`, and every other `/api/*` endpoint is called — the JavaScript just receives the HTML response body and calls `.json()` on it. `<!DOCTYPE` is not JSON, so the client throws `Unexpected token '<'`. The user sees a stack trace, not a captcha.

Rule of thumb: **on `/api/*` endpoints, the only safe actions are `Block` and `Skip`.** Save Challenge actions for full HTML page loads (`/`, `/impressum`, `/datenschutzerklaerung`).

Also worth knowing: `cf.client.bot` is the **Verified Bot** boolean — it only returns `true` for search engines and monitoring services on Cloudflare's known-bot list (Googlebot, Bingbot, UptimeRobot, etc.). Every real browser is `false`. So an expression like `not cf.client.bot` matches every human visitor, not just malicious scripts. Do not use it as the sole gate for challenging on an API.

Leave this slot empty until you have a concrete pattern (specific ASN, user-agent, path) to Block.

### Rule 5 — Reserved for incident response

Leave the last slot empty. When you see a real abuse pattern in Cloudflare Analytics (a specific ASN scraping, a particular User-Agent, a JA3 fingerprint), you spend the slot to Block or Challenge that pattern immediately without evicting a load-bearing rule.

## What is intentionally NOT enabled

- **Bot Fight Mode** — the free "block anything non-browser" toggle under Security → Bots. Blocks curl, UptimeRobot, and every SDK. Traded away in favour of the granular Custom Rules above.
- **Super Bot Fight Mode** — paid.
- **JavaScript Detections** — Security → Settings → *JavaScript detections* — MUST be OFF. When enabled, Cloudflare rewrites every HTML response to inject a per-request inline `<script>` (`/cdn-cgi/challenge-platform/scripts/jsd/main.js` bootstrapper). The bootstrap uses a fresh timestamp on every request, so its SHA-256 changes every load — no CSP hash allowlist can cover it. Against the strict `script-src 'self' https://unpkg.com https://umami.addrlens.de` shipped by `app/main.py`, the browser blocks the injection and prints a CSP violation on every page load. The site keeps working (JSD is a bot-signal, not a functional dependency) but the console noise pollutes DevTools and any browser-side Sentry SDK. If a future feature genuinely needs JSD, either downgrade CSP to include `'unsafe-inline'` (regresses XSS hardening) or move to a nonce-based CSP where Cloudflare and the origin both apply the same per-request nonce.
- **Cloudflare AI Gateway** for the Workers AI calls — not needed at this scale; adds an extra hop for the origin, and the app already retries locally on remote failure. Revisit when the Workers AI monthly bill matters.

## Verifying the rules are live

After saving, the rules take effect at the edge within seconds — no dashboard restart or origin restart is required.

Test each layer from a machine that is NOT the Hetzner box (a local Mac, a phone on cellular, etc.), so the requests actually reach Cloudflare's edge:

```bash
# Rate Limiting Rule — should return 403 after the 6th rapid request.
for i in $(seq 1 8); do
  curl -sS -o /dev/null -w "#$i  %{http_code}\n" \
    "https://addrlens.de/api/history?lat=52.55&lon=13.47&street=X&hnr=1&plz=13088"
done

# Rule 2 — empty UA should return 403 immediately.
curl -sS -o /dev/null -w "%{http_code}\n" -A "" https://addrlens.de/api/lookup?address=Test
```

Rules 3 and 4 are currently disabled/reserved (see above). If you re-enable a challenge-style rule in the future, verify it from a VPN exit outside your allowlist. Cloudflare **Security → Events** shows every request that matched a rule, with the exact rule name and IP — start there before adding a new rule.

## When to revisit

- **You upgrade to Cloudflare Pro** — Rate Limiting Rule quota goes up, additional actions (Managed Challenge, JS Challenge) become available, longer counting periods become available. Rewrite the Rate Limiting Rule to use Managed Challenge instead of Block for a softer user experience.
- **Workers AI cost gets noticeable** — a bad actor may be bypassing rate limits via distributed source IPs. Rotate the /api/history rule to use `Verified Bot` as an additional counting characteristic or add a Custom Rule that requires a fingerprint on the endpoint (e.g., an app-controlled header the frontend sends).
- **Real users complain about friction** — Cloudflare **Security → Events** shows challenge/block hit counts per rule. If a rule bites more legitimate users than bots, loosen the expression or remove it. Rule 3-style geo/challenge rules on `/api/*` are the most likely culprits — see the Rule 3 post-mortem above before adding a new one.
