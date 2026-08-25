# Hetzner deploy — step-by-step

Zero-to-live playbook for deploying addrlens to a fresh Hetzner box behind a Cloudflare Tunnel. Distilled from `ops/deploy/README.md` and hardened against issues surfaced during local Docker smoke testing.

## Pre-flight (do once, off-box)

- **Provision Hetzner CX22 or CPX21** (x86_64, at least 4 GB RAM, at least 40 GB disk). Choose the **Debian 13 (trixie)** image — `bootstrap.sh` targets Debian's Docker apt repo. Add your SSH public key during creation.
- **Attach a Primary IPv4 to the box.** Hetzner's newer plans only give you IPv6 out of the box; without a public v4 the machine gets a CGNAT `100.64.0.0/10` LAN address and has no route to the public internet (GitHub, Docker Hub, Hugging Face all fail to resolve or connect). Console → **Servers → your box → Networking → Add Primary IPv4** (~€0.60/month), or attach an unassigned Primary IPv4 from the **Primary IPs** tab. After attaching, `sudo reboot` the box so cloud-init picks up the new v4 lease.
- **Create a Cloudflare Zero-Trust Tunnel** in the CF dashboard. Copy the `TUNNEL_TOKEN`. Under the tunnel's *Public Hostname* config point `addrlens.de` at `http://app:8001`. The DNS record is created automatically by the tunnel.
  - **DNS conflict on apex:** if the domain was registered through Hetzner or has any existing A/AAAA at the apex (`addrlens.de` bare), Cloudflare will refuse to create its CNAME with *"A DNS record with this name already exists."* In the CF **DNS → Records** panel, delete the apex `A` and `AAAA` records (typically pointing at Hetzner's shared web hosting, e.g. `88.198.219.246`). Keep the MX / SRV / TXT / `autoconfig` CNAME rows — those are email routing and are unrelated. Then retry the tunnel Public Hostname add. Optionally repeat for `www` if you want both apex and `www` to route through the tunnel.
- **Set up a GitHub deploy key** for the box (before the first `git clone`, because password auth is disabled on github.com and the repo may be private).
  - On the box: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_addrlens -N ""` and `cat ~/.ssh/id_ed25519_addrlens.pub`.
  - On GitHub: `https://github.com/saptadip/addrlens/settings/keys` → **Add deploy key**. Title `hetzner-addrlens-prod`. Paste the public key. **Do not** enable write access.
  - On the box, add an SSH config entry so `git` picks the right key:
    ```bash
    cat >> ~/.ssh/config <<'EOF'
    Host github.com
      HostName github.com
      User git
      IdentityFile ~/.ssh/id_ed25519_addrlens
      IdentitiesOnly yes
    EOF
    chmod 600 ~/.ssh/config
    ssh -T git@github.com   # expect: "Hi saptadip/addrlens! You've successfully authenticated…"
    ```
- **Get Sentry DSNs** for the `addrlens-app` and `addrlens-inference` projects. Optional — Sentry initialization is env-guarded, so the DSN variables can be left unset to skip Sentry entirely.

## First deploy

- **SSH in and prepare the tree.** Clone via SSH (uses the deploy key set up above).
  ```bash
  ssh sapta@<box-ip>
  sudo mkdir -p /srv/addrlens && sudo chown sapta:sapta /srv/addrlens
  cd /srv/addrlens
  git clone git@github.com:saptadip/addrlens.git repo
  ```
- **Bootstrap the host.** Installs docker (from the Debian Docker apt repo), ufw rules, swap, and the systemd timer. Idempotent.
  ```bash
  cd /srv/addrlens/repo/v0.1
  sudo bash ops/deploy/bootstrap.sh
  ```
- **Log out and back in** so the `sapta` user picks up the newly-added `docker` group.
- **Fetch the GGUF model file** (about 940 MB, one time). Debian 13 ships without `pip` and blocks system-wide pip installs via PEP 668, so we skip the `hf` CLI and pull the file directly:
  ```bash
  mkdir -p /srv/addrlens/models
  curl -L -o /srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
      "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf?download=true"
  ls -lh /srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
  ```
- **Create `/srv/addrlens/.env.production`** from the template. Required values: `TUNNEL_TOKEN`, `SENTRY_DSN_APP`, `SENTRY_DSN_INFERENCE`.
  ```bash
  cp /srv/addrlens/repo/v0.1/.env.production.example /srv/addrlens/.env.production
  chmod 600 /srv/addrlens/.env.production
  vim /srv/addrlens/.env.production
  ```
  Back the file up to your password manager. It is git-ignored and never leaves the box.
- **Build images cold** (roughly 10 minutes — llama-cpp-python compiles from source; `build-essential` is already installed in the inference image).
  ```bash
  cd /srv/addrlens/repo/v0.1
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
      --env-file /srv/addrlens/.env.production build
  ```
- **Seed the OSM snapshot before the first `up`** — the app reads this file at boot.
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
      --env-file /srv/addrlens/.env.production \
      run --rm --entrypoint python app -m scripts.refresh_osm_amenities
  ls -lh /srv/addrlens/data/osm/berlin-amenities.json   # expect ~13 MB
  ```
- **Bring the stack up.**
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
      --env-file /srv/addrlens/.env.production up -d
  docker compose logs -f cloudflared   # look for "Registered tunnel connection"
  ```
- **Verify through Cloudflare.**
  ```bash
  curl -sSf https://addrlens.de/health   # {"status":"ok"}
  curl -sSf https://addrlens.de/ready    # {"status":"ready","city":"berlin"}
  curl -sSf 'https://addrlens.de/api/lookup?address=Bergmannstra%C3%9Fe+27,+10961' | jq '.lens|keys'
  ```

## Post-deploy

- **SSH hardening — done manually, once.** Automating this in a script risks locking yourself out.
  ```bash
  sudo vim /etc/ssh/sshd_config
  # PermitRootLogin no
  # PasswordAuthentication no
  # PubkeyAuthentication yes
  sudo systemctl reload sshd
  ```
  Keep the current session open. Open a NEW terminal window, confirm you can SSH in with the pubkey, and only then close the original session.
- **Verify the weekly OSM refresh timer.**
  ```bash
  systemctl list-timers refresh-osm-amenities.timer   # NEXT column should read Sunday 03:00
  ```

## Updates

Run from the box after `git push origin main` has landed the new code:

```bash
cd /srv/addrlens/repo/v0.1
./ops/deploy/update.sh
```

The script pulls the latest `main`, rebuilds the images, restarts the stack, and gates on `/ready`. The deployed SHA is written to `/srv/addrlens/last-deployed.sha` so rollback knows the previous version.

## Rollback

```bash
./ops/deploy/rollback.sh           # revert to the SHA in /srv/addrlens/last-deployed.sha
./ops/deploy/rollback.sh <sha>     # revert to any specific SHA
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

- **502 from Cloudflare.** The origin app is restarting (likely mid-`update.sh`) or `cloudflared` has lost its connection. Check `docker compose ps` and `docker compose logs cloudflared`.
- **`/ready` returns 503 forever.** The `Index` boot failed. Two common causes:
  - Berlin `gdi.berlin.de` WFS is under maintenance — check the maintenance HTML with `curl https://gdi.berlin.de/services/wfs/schulen?...&outputFormat=application/json | head`. If HTML, wait for the Senate to bring it back up.
  - OSM snapshot missing. Run `ls /srv/addrlens/data/osm/berlin-amenities.json` — expect a file over 10 MB. If missing, re-run the seed step from the first-deploy section.
- **Inference OOM.** Run `docker inspect v0.1-inference-1 | grep -i oom`. If `OOMKilled: true`, either increase `mem_limit` in `docker-compose.prod.yml`, increase swap, drop to a smaller quant (Q3_K_M), or upgrade to a larger box.
- **Cloudflare Tunnel disconnected.** Try `docker compose restart cloudflared`. If it keeps failing, the `TUNNEL_TOKEN` may be stale — regenerate it in the Cloudflare dashboard, update `/srv/addrlens/.env.production`, and restart the service.
- **`git clone` fails with "Network is unreachable" or "Failed to connect to github.com port 443 after 1 ms".** The box has no IPv4 default route — a fresh Hetzner box without a Primary IPv4 sits on a CGNAT `100.64.0.0/10` LAN with no path to the public internet. Attach a Primary IPv4 in the Hetzner console as described in Pre-flight and reboot.
- **`git clone` prompts for a password and rejects it** ("Password authentication is not supported for Git operations"). GitHub disabled HTTPS password auth in 2021. Use the SSH deploy-key path in Pre-flight and clone via `git@github.com:saptadip/addrlens.git`.
- **`bootstrap.sh` fails with `404 Not Found` on `https://download.docker.com/linux/ubuntu ... Release`.** You provisioned an Ubuntu image instead of Debian, or a Debian image with the wrong repo pinned. `bootstrap.sh` targets `linux/debian`; either rebuild the box as Debian 13 (trixie) or edit the script back to `linux/ubuntu` with `$(lsb_release -cs)`.
- **Cloudflare Tunnel wizard: "A DNS record with this name already exists."** An A/AAAA/CNAME sits at the apex (`addrlens.de`). Delete only that apex record (and its `www` twin if you want both routes to go through the tunnel). Preserve the MX / SRV / TXT / `autoconfig` rows — they are email routing, not tunnel-related.
