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

### Rule 3 — Country friction for API endpoints

The target audience is people evaluating Berlin addresses. Most traffic will originate from EU countries plus a handful of English-speaking ones. Anything outside this set gets a Managed Challenge — annoying for one lookup, invisible after solving. Adjust the allow-list as your audience takes shape.

- **Name:** `api — challenge unusual countries`
- **Expression:** `(starts_with(http.request.uri.path, "/api/")) and not (ip.geoip.country in {"DE" "AT" "CH" "FR" "NL" "PL" "US" "GB"})`
- **Action:** **Managed Challenge**

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

For Rule 3 (country challenge) and Rule 4 (bot challenge), test with a browser from a country in and outside your allow-list, or use a VPN. Cloudflare **Security → Events** shows every request that matched a rule, with the exact rule name and IP.

## When to revisit

- **You upgrade to Cloudflare Pro** — Rate Limiting Rule quota goes up, additional actions (Managed Challenge, JS Challenge) become available, longer counting periods become available. Rewrite the Rate Limiting Rule to use Managed Challenge instead of Block for a softer user experience.
- **Workers AI cost gets noticeable** — a bad actor may be bypassing rate limits via distributed source IPs. Rotate the /api/history rule to use `Verified Bot` as an additional counting characteristic or add a Custom Rule that requires a fingerprint on the endpoint (e.g., an app-controlled header the frontend sends).
- **Real users complain about friction** — Cloudflare **Security → Events** shows challenge/block hit counts per rule. If a rule bites more legitimate users than bots, loosen the expression or remove it. Rule 4 is the most likely culprit — remove it first.
