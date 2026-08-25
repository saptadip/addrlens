# Deploy operations — addrlens.de

## First deploy on a fresh box

Prerequisites: Ubuntu 24.04 x86_64, sudo user `sapta`, SSH access.

1. **Clone the repo:**

   ```bash
   ssh sapta@<box-ip>
   sudo mkdir -p /srv/addrlens
   sudo chown sapta:sapta /srv/addrlens
   cd /srv/addrlens
   git clone <git-remote-url> repo
   ```

2. **Bootstrap the host:**

   ```bash
   cd /srv/addrlens/repo/v0.1
   sudo bash ops/deploy/bootstrap.sh
   # Installs docker, ufw, swap, systemd timer. Idempotent.
   ```

3. **Log out and back in** so the `sapta` user picks up the `docker` group.

4. **Fetch the model file** (~1 GB, once):

   ```bash
   pip install --user huggingface_hub[cli]
   hf download bartowski/Qwen2.5-1.5B-Instruct-GGUF \
       Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
       --local-dir /srv/addrlens/models
   ls -lh /srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
   ```

5. **Fill in `/srv/addrlens/.env.production`** using `.env.production.example` as the template. Required values: `TUNNEL_TOKEN`, `SENTRY_DSN_APP`, `SENTRY_DSN_INFERENCE`.

   ```bash
   cp /srv/addrlens/repo/v0.1/.env.production.example /srv/addrlens/.env.production
   chmod 600 /srv/addrlens/.env.production
   vim /srv/addrlens/.env.production
   ```

   After editing, back the file up to your password manager. It is git-ignored and never leaves the box.

6. **Build images cold** (~10 min: llama-cpp-python wheel + shapely + fastapi):

   ```bash
   cd /srv/addrlens/repo/v0.1
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       --env-file /srv/addrlens/.env.production \
       build
   ```

7. **Run the first OSM snapshot** (needed BEFORE `up -d` — the app reads this file at boot):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       --env-file /srv/addrlens/.env.production \
       run --rm --entrypoint python app -m scripts.refresh_osm_amenities
   ls -lh /srv/addrlens/data/osm/berlin-amenities.json
   ```

8. **Bring the stack up:**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       --env-file /srv/addrlens/.env.production \
       up -d
   docker compose logs -f cloudflared
   # Expect: "Registered tunnel connection connIndex=0 ..."
   ```

9. **Sanity-check through Cloudflare:**

   ```bash
   curl -sSf https://addrlens.de/health   # {"status":"ok"}
   curl -sSf https://addrlens.de/ready    # {"status":"ready","city":"berlin"}
   ```

## Updates

```bash
cd /srv/addrlens/repo/v0.1
./ops/deploy/update.sh
```

## Rollback

```bash
cd /srv/addrlens/repo/v0.1
./ops/deploy/rollback.sh           # to the SHA in /srv/addrlens/last-deployed.sha
./ops/deploy/rollback.sh <sha>     # to any SHA
```

## SSH hardening (not scripted — do manually once)

Auto-modifying `/etc/ssh/sshd_config` risks lockout. After confirming pubkey login works:

```bash
sudo vim /etc/ssh/sshd_config
# Set: PermitRootLogin no
#      PasswordAuthentication no
#      PubkeyAuthentication yes
sudo systemctl reload sshd
# KEEP THE CURRENT SESSION OPEN. Open a NEW terminal, try to SSH in fresh.
# Only close the original session after a fresh session works.
```

Optional: move SSH to a random high port. Update `ufw allow <port>/tcp comment 'SSH'` accordingly.

## Verifying the OSM refresh timer

```bash
systemctl list-timers refresh-osm-amenities.timer
# NEXT column should show next Sunday 03:00.
sudo systemctl start refresh-osm-amenities.service   # force a run now
sudo journalctl -u refresh-osm-amenities.service -n 100 --no-pager
```

## Watching runtime

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production ps
docker compose logs -f app
docker compose logs -f inference
docker compose logs -f cloudflared
docker stats
```

## Common gotchas

- **502 from CF:** origin app is restarting (during `update.sh`), or `cloudflared` lost its connection. Check `docker compose ps` and `docker compose logs cloudflared`.
- **/ready 503 forever:** `Index` boot failed (Berlin WFS down, or OSM snapshot missing). Check `docker compose logs app`. If OSM missing: `ls /srv/addrlens/data/osm/berlin-amenities.json` — should be > 10 MB. If empty, run step 7 above.
- **Inference OOM:** `docker inspect inference | grep -i oom`. If `OOMKilled: true`, the `mem_limit` (2800m) is too tight. Options: increase swap, drop to a smaller quant (Q3_K_M), or upgrade the box.
- **CF Tunnel disconnected:** `docker compose restart cloudflared`. If it keeps failing, `TUNNEL_TOKEN` may be stale — regenerate in the CF dashboard.
