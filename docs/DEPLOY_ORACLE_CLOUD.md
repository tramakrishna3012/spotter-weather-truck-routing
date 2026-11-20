# Deploying Spotter on Oracle Cloud Always Free (OCI)

This guide deploys the full **Spotter — Weather-Aware Truck Routing** production stack (**React + TypeScript SPA, Django/DRF API, PostgreSQL 16, Redis 7, and Caddy auto-HTTPS**) on a single **Oracle Cloud Always Free Ubuntu VM** with **zero sleep / zero cold starts**.

## Architecture on OCI

```text
Internet (HTTPS 443)
  └── Caddy 2 (Auto Let's Encrypt TLS + Security Headers, blocks external /metrics)
        ├── /api/*  ──► backend:8000 (Django + DRF + Gunicorn, non-root)
        │                 ├──► postgres:5432 (PostgreSQL 16, internal network only)
        │                 └──► redis:6379    (Redis 7 + password auth, internal only)
        └── /*      ──► frontend:80  (Nginx serving React + MapLibre SPA, same-origin)
```

Serving both the React SPA and `/api/*` under **one HTTPS domain** gives same-origin `HttpOnly; Secure; SameSite=Lax` guest session cookies and eliminates cross-origin preflights.

---

## Step 1 — Create Your Oracle Cloud Always Free VM

1. Sign in to [Oracle Cloud Console](https://cloud.oracle.com/) → **Compute → Instances → Create Instance**.
2. **Image:** `Canonical Ubuntu 24.04` (or `22.04`).
3. **Shape (Always Free eligible):**
   - **Recommended:** `VM.Standard.A1.Flex` (**Ampere ARM64**, e.g., 2 OCPUs / 12 GB RAM — fast builds & plenty of headroom).
   - **Fallback (if Ampere A1 capacity is temporarily full in your region):** `VM.Standard.E2.1.Micro` (AMD64, 1 OCPU / 1 GB RAM — our bootstrap script automatically adds a 2 GB swapfile so builds succeed smoothly).
4. **Networking:** Ensure **Assign a public IPv4 address** is checked.
5. **SSH Keys:** Download or paste your SSH public key, then click **Create**.
6. Copy the instance's **Public IPv4 Address**.

---

## Step 2 — Open Ports 80 & 443 in OCI VCN Security List

1. On the Instance details page, click the **Subnet** link → click the **Default Security List**.
2. Click **Add Ingress Rules** and add two rules:
   - **HTTP:** Source CIDR `0.0.0.0/0`, IP Protocol `TCP`, Destination Port Range `80`
   - **HTTPS:** Source CIDR `0.0.0.0/0`, IP Protocol `TCP`, Destination Port Range `443`
   - *(Optional HTTP/3 QUIC)*: Source CIDR `0.0.0.0/0`, IP Protocol `UDP`, Destination Port Range `443`

---

## Step 3 — Point Your Free Domain (GitHub Student Pack) to OCI

Using your free 1-year domain from **Name.com**, **Namecheap (`.me`)**, or **`.TECH`** (GitHub Student Developer Pack):
1. Open your domain registrar's DNS settings.
2. Add an **`A` record**:
   - **Host / Name:** `spotter` (for `spotter.yourdomain.tech`) or `@` (for root domain)
   - **Value / Target:** `<YOUR_OCI_PUBLIC_IPV4>`
   - **TTL:** `300` (5 minutes)
3. Verify DNS propagation before starting Caddy:
   ```bash
   dig +short spotter.yourdomain.tech
   ```

---

## Step 4 — Bootstrap the OCI Ubuntu VM

SSH into your VM and run the included bootstrap script (it installs Docker Engine + Compose, adds 2 GB swap if RAM < 3 GB, and opens ports 80/443 in Oracle Ubuntu's local `iptables`):

```bash
ssh -i /path/to/your-key.pem ubuntu@<YOUR_OCI_PUBLIC_IPV4>

git clone https://github.com/tramakrishna3012/spotter-weather-truck-routing.git
cd spotter-weather-truck-routing
chmod +x deploy/oracle/bootstrap-ubuntu.sh
sudo ./deploy/oracle/bootstrap-ubuntu.sh

# Re-login once so the ubuntu user picks up docker group permissions
exit
```

---

## Step 5 — Create Production `.env` (Never Commit!)

SSH back in, copy `.env.example`, and fill in your real production values:

```bash
cd ~/spotter-weather-truck-routing
cp .env.example .env
chmod 600 .env
```

Generate strong random secrets right on the VM:
```bash
python3 -c 'import secrets; print("DJANGO_SECRET_KEY=" + secrets.token_urlsafe(64))'
python3 -c 'import secrets; print("POSTGRES_PASSWORD=" + secrets.token_urlsafe(24))'
python3 -c 'import secrets; print("REDIS_PASSWORD=" + secrets.token_urlsafe(24))'
```

Edit `.env` (`nano .env`) and set these production keys (replace placeholders with your real values):

```env
# --- Domain & Auto-HTTPS (Caddy) ---
DOMAIN=spotter.yourdomain.tech
ACME_EMAIL=you@yourdomain.tech

# --- Core Django Security (Fail-Closed Production) ---
APP_ENV=production
DATA_MODE=live
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<generated-64-char-secret>
FRONTEND_ORIGIN=https://spotter.yourdomain.tech
ALLOWED_HOSTS=spotter.yourdomain.tech
DJANGO_CORS_ALLOWED_ORIGINS=https://spotter.yourdomain.tech
SESSION_COOKIE_SECURE=true

# --- Internal Docker Postgres & Redis ---
POSTGRES_DB=spotter
POSTGRES_USER=spotter
POSTGRES_PASSWORD=<generated-postgres-password>
REDIS_PASSWORD=<generated-redis-password>
REDIS_MAXMEMORY=128mb

# --- External Providers (see docs/PREREQUISITES_AND_KEYS.md) ---
HERE_API_KEY=<your-here-routing-and-geocoding-key>
HERE_ROUTING_BASE_URL=https://router.hereapi.com/v8
HERE_GEOCODING_BASE_URL=https://geocode.search.hereapi.com/v1
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1
OPEN_METEO_API_KEY=

# --- Licensed MapLibre Basemap (baked into frontend build) ---
VITE_MAP_STYLE_URL=<your-licensed-style-json-url>
VITE_MAP_PUBLIC_TOKEN=<optional-referer-restricted-token>

# --- Worker & Runtime Sizing ---
ENABLE_ASYNC_PLANNING=false
WEB_CONCURRENCY=2
GUNICORN_THREADS=2
PLANNING_CONCURRENCY=4
```

> **Note:** On `APP_ENV=production`, Django enforces fail-closed checks at startup — `DATA_MODE=live`, `DJANGO_DEBUG=false`, strong `DJANGO_SECRET_KEY`, `HERE_API_KEY`, PostgreSQL `DATABASE_URL`, explicit `ALLOWED_HOSTS`, and `SESSION_COOKIE_SECURE=true` are all required.
> For initial pre-key UI testing before obtaining live keys, temporarily set `APP_ENV=staging`, `DATA_MODE=fixture`, `DJANGO_DEBUG=false`, and `SESSION_COOKIE_SECURE=true` (the UI will display the unmistakable **Sample data (Fixture mode)** badge).

---

## Step 6 — Launch & Verify Production Stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Verify TLS, backend health, database, cache, and provider readiness:

```bash
curl -fsS https://spotter.yourdomain.tech/api/v1/health/live
curl -fsS https://spotter.yourdomain.tech/api/v1/health/ready
```

Expected readiness response:
```json
{"status": "ready", "data_mode": "live", "checks": {"database": "ok", "cache": "ok", "providers": "ok"}}
```

Verify `/metrics` is blocked externally (returns `403`):
```bash
curl -I https://spotter.yourdomain.tech/metrics
```

Open `https://spotter.yourdomain.tech` in your browser and run a live route test (e.g., Denver, CO → Salt Lake City, UT).

---

## Step 7 — Optional One-Click Redeploys via GitHub Actions

To redeploy from GitHub Actions ([.github/workflows/deploy-oracle.yml](../.github/workflows/deploy-oracle.yml)), add 4 repository secrets under **Settings → Secrets and variables → Actions**:
- `OCI_HOST`: Your OCI Public IPv4 address
- `OCI_USER`: `ubuntu`
- `OCI_SSH_KEY`: Private SSH key for the VM
- `OCI_DEPLOY_PATH`: `/home/ubuntu/spotter-weather-truck-routing`

Then trigger **Actions → Deploy to Oracle Cloud (OCI) → Run workflow**.

---

## Operations & Maintenance

- **View logs:** `docker compose -f docker-compose.prod.yml logs -f backend caddy`
- **Enable optional Celery worker:** `docker compose -f docker-compose.prod.yml --profile async up -d --build` (set `ENABLE_ASYNC_PLANNING=true` in `.env`)
- **Database backup:**
  ```bash
  docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U spotter spotter | gzip > spotter-backup-$(date +%F).sql.gz
  ```
- **Optional Datadog / Sentry monitoring (GitHub Student Pack):** You can install the Datadog Agent directly on the OCI Ubuntu host to collect Docker metrics & scrape `http://127.0.0.1` internal container health without exposing `/metrics` publicly.
