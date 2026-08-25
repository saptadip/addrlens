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
