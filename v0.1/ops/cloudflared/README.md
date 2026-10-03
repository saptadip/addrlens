# Cloudflare Tunnel — addrlens.de

## Creating the tunnel (once)

1. Cloudflare dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Connector type: **Cloudflared**.
3. Tunnel name: `addrlens-prod`.
4. Environment: **Docker**. The dashboard shows a `docker run cloudflare/cloudflared:latest tunnel --token eyJ...` snippet.
5. Copy **only the token** (the long `eyJ...` string). Paste it into `/srv/addrlens/.env.production` as `TUNNEL_TOKEN=eyJ...`. Ignore the rest of the snippet — the compose file supplies the container spec.

## Public hostname routing

Wizard → **Public Hostnames** step:

| Field | Value |
|---|---|
| Subdomain | *(blank — apex)* |
| Domain | `addrlens.de` |
| Path | *(blank — all paths)* |
| Service Type | HTTP |
| URL | `app:8001` |

**Additional Application Settings:**
- HTTP Host Header: `addrlens.de`
- HTTP2 connection: On
- Connection timeout: 30 s

The wizard automatically creates a proxied CNAME `addrlens.de` → `<tunnel-id>.cfargotunnel.com`. If existing A/AAAA records exist on apex, accept the wizard's "replace" prompt.

### Hamburg subdomain

Add a second Public Hostname on the same tunnel for Hamburg:

| Field | Value |
|---|---|
| Subdomain | `hamburg` |
| Domain | `addrlens.de` |
| Path | *(blank — all paths)* |
| Service Type | HTTP |
| URL | `app-hh:8002` |

**Additional Application Settings:**
- HTTP Host Header: `hamburg.addrlens.de`
- HTTP2 connection: On
- Connection timeout: 30 s

Wizard creates `hamburg.addrlens.de` proxied CNAME to the same tunnel. `app-hh` container (docker-compose.prod.yml) runs `CITY=hamburg` on port 8002.

## Token rotation

If the token is compromised or you want to rotate:

1. CF dashboard → Zero Trust → Networks → Tunnels → `addrlens-prod` → delete.
2. Create a new tunnel with the same public hostname config.
3. Update `TUNNEL_TOKEN=` in `/srv/addrlens/.env.production` on the box.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file /srv/addrlens/.env.production up -d cloudflared` — restarts only cloudflared with the new token.

## Troubleshooting

- **Tunnel status "disconnected" in CF dashboard:**
  ```bash
  docker compose logs cloudflared --tail=100
  ```
  Look for auth failures (rotate token) or network errors (check outbound 443).

- **Users see CF error page but origin is healthy:**
  Check CF dashboard → Zero Trust → Networks → Tunnels for connection status.
  ```bash
  docker compose restart cloudflared
  ```

- **Want to bypass CF for debugging:** you can't — the box has no public port other than SSH. Debug via `curl -sSf http://localhost:8001/health` from inside the box (or `docker compose exec app curl -sSf http://127.0.0.1:8001/health`).

## CSP {#csp}

### Symptom

Browser console on `berlin.addrlens.de` / `hamburg.addrlens.de` reports:

```
Executing inline script violates the following Content Security Policy directive
'script-src 'self' https://unpkg.com https://umami.addrlens.de 'sha256-...''.
Either the 'unsafe-inline' keyword, a hash ('sha256-M3cFExag...'),
or a nonce ('nonce-...') is required to enable inline execution.
```

The blocked script is at the bottom of the served HTML and looks like:

```js
(function(){function c(){var b=a.contentDocument||...
window.__CF$cv$params={r:'<token>',t:'<token>'};
...challenge-platform/scripts/jsd/main.js...})();
```

### Root cause

**Cloudflare's edge injects this inline script**, not AddrLens's code. It's part of Cloudflare's **JavaScript Detections** feature (sometimes exposed as "Bot Fight Mode"), which inserts a per-request browser-fingerprinting tracker. The injection happens AFTER FastAPI serves the HTML, so the server's `Content-Security-Policy` header does not — and cannot — cover it.

The injected script's content includes per-request tokens (`r` and `t`), so its SHA-256 hash changes on every response. A hash-based CSP whitelist is impossible.

### Fix

Disable Cloudflare's JavaScript Detections / Bot Fight Mode for the AddrLens zone:

1. Cloudflare dashboard → select the `addrlens.de` zone
2. **Security → Bots → Configure Bot Fight Mode** → toggle **off**
3. Also check **Security → Settings → Browser Integrity Check** — leave on (that's an HTTP-header check, not an inline-script injection)
4. Also check **Security → Settings → JavaScript Detections** if present as a separate toggle — turn **off**
5. Hard-refresh `https://berlin.addrlens.de/` and confirm the browser console no longer reports the CSP violation

Why this is safe for AddrLens: the site is a stateless public read-only API with no login, no form submissions, and no abuse surface that JavaScript Detections would help defend. Cloudflare's own documentation lists these features as targeted at sites with user accounts, comment forms, or e-commerce flows — none of which apply here.

### Why not add CF to the CSP?

- **By hash:** per-request tokens make the hash change every response. Impossible.
- **By `'unsafe-inline'`:** defeats the entire CSP. Rejected.
- **By origin:** the injected script has no `src=` — it's a true inline `<script>...</script>` block. Origin-based `script-src` entries don't cover it.
- **By CF Response Header Transform rule:** Cloudflare does support rewriting response headers, including CSP. If you need the JS Detections feature AND strict CSP, the only path is a Transform Rule that strips the injected script before it reaches the browser. More complexity than disabling the feature.

### Related

The `JSON-LD` inline script in `web/index.html` IS covered by a SHA-256 hash computed at FastAPI boot (`_compute_jsonld_hash` in `app/main.py`) — that's a separate inline script and not the one triggering the CF error above. See `app/main.py` CSP block for the full rationale.
