#!/usr/bin/env bash
# Interactive, fail-safe production `.env` generator and launcher for Oracle Cloud (OCI).
# Keeps all secrets strictly local on the VM (chmod 600 .env, gitignored).
#
# Usage (on your OCI Ubuntu VM inside ~/spotter-weather-truck-routing):
#   ./deploy/oracle/configure-env.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

echo "============================================================"
echo "  Spotter — Oracle Cloud Production Setup Wizard"
echo "============================================================"
echo ""

read -r -p "1. Enter your full subdomain (e.g. spotter.tramakrishna.codes): " DOMAIN
DOMAIN="$(echo "${DOMAIN}" | tr '[:upper:]' '[:lower:]' | xargs)"
if [[ -z "${DOMAIN}" ]]; then
  echo "Error: Domain cannot be empty." >&2
  exit 1
fi

read -r -p "2. Enter your email for Let's Encrypt HTTPS notifications: " ACME_EMAIL
ACME_EMAIL="$(echo "${ACME_EMAIL}" | xargs)"
ACME_EMAIL="${ACME_EMAIL:-ops@${DOMAIN}}"

echo ""
echo "3. Select deployment mode:"
echo "   [1] live    — Production live mode (requires HERE_API_KEY + licensed MapLibre style URL)"
echo "   [2] fixture — Staging preview mode (starts immediately with labeled Sample data; switch to live anytime)"
read -r -p "Choose [1 or 2]: " MODE_CHOICE

HERE_API_KEY=""
OPEN_METEO_API_KEY=""
VITE_MAP_STYLE_URL=""
VITE_MAP_PUBLIC_TOKEN=""

if [[ "${MODE_CHOICE}" == "1" ]]; then
  APP_ENV="production"
  DATA_MODE="live"
  echo ""
  read -r -s -p "4. Enter HERE_API_KEY (input hidden): " HERE_API_KEY
  echo ""
  if [[ -z "${HERE_API_KEY}" ]]; then
    echo "Error: HERE_API_KEY is required for live mode." >&2
    exit 1
  fi
  read -r -p "5. Enter VITE_MAP_STYLE_URL (licensed MapLibre style JSON URL): " VITE_MAP_STYLE_URL
  read -r -p "6. Enter VITE_MAP_PUBLIC_TOKEN (press Enter if none): " VITE_MAP_PUBLIC_TOKEN
  read -r -s -p "7. Enter OPEN_METEO_API_KEY (press Enter for non-commercial free tier): " OPEN_METEO_API_KEY
  echo ""
elif [[ "${MODE_CHOICE}" == "2" ]]; then
  APP_ENV="staging"
  DATA_MODE="fixture"
  echo ""
  read -r -p "4. Optional VITE_MAP_STYLE_URL (press Enter to use default dev basemap): " VITE_MAP_STYLE_URL
  read -r -p "5. Optional VITE_MAP_PUBLIC_TOKEN (press Enter if none): " VITE_MAP_PUBLIC_TOKEN
else
  echo "Error: Please enter 1 or 2." >&2
  exit 1
fi

# Generate strong cryptographic secrets locally on the VM (never printed).
DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
REDIS_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"

# Preserve existing DB/Redis passwords if re-running on an already initialized Postgres volume!
if [[ -f "${ENV_FILE}" ]]; then
  EXISTING_PG_PASS="$(grep -E '^POSTGRES_PASSWORD=' "${ENV_FILE}" | head -n1 | cut -d'=' -f2- || true)"
  EXISTING_REDIS_PASS="$(grep -E '^REDIS_PASSWORD=' "${ENV_FILE}" | head -n1 | cut -d'=' -f2- || true)"
  if [[ -n "${EXISTING_PG_PASS}" ]]; then
    POSTGRES_PASSWORD="${EXISTING_PG_PASS}"
    echo "Preserving existing POSTGRES_PASSWORD so existing Postgres volume stays compatible."
  fi
  if [[ -n "${EXISTING_REDIS_PASS}" ]]; then
    REDIS_PASSWORD="${EXISTING_REDIS_PASS}"
  fi
fi

umask 077
cat > "${ENV_FILE}" <<EOF
# Auto-generated locally on OCI VM by deploy/oracle/configure-env.sh
# NEVER commit this file to Git.

DOMAIN=${DOMAIN}
ACME_EMAIL=${ACME_EMAIL}

APP_ENV=${APP_ENV}
DATA_MODE=${DATA_MODE}
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}

FRONTEND_ORIGIN=https://${DOMAIN}
ALLOWED_HOSTS=${DOMAIN}
DJANGO_CORS_ALLOWED_ORIGINS=https://${DOMAIN}
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN}
SESSION_COOKIE_SECURE=true

POSTGRES_DB=spotter
POSTGRES_USER=spotter
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_MAXMEMORY=128mb

HERE_API_KEY=${HERE_API_KEY}
HERE_ROUTING_BASE_URL=https://router.hereapi.com/v8
HERE_GEOCODING_BASE_URL=https://geocode.search.hereapi.com/v1

OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1
OPEN_METEO_API_KEY=${OPEN_METEO_API_KEY}

VITE_API_BASE_URL=
VITE_MAP_STYLE_URL=${VITE_MAP_STYLE_URL}
VITE_MAP_PUBLIC_TOKEN=${VITE_MAP_PUBLIC_TOKEN}

ENABLE_ASYNC_PLANNING=false
WEB_CONCURRENCY=2
GUNICORN_THREADS=2
PLANNING_CONCURRENCY=4
PROVIDER_CONNECT_TIMEOUT_SECONDS=5
PROVIDER_READ_TIMEOUT_SECONDS=20
PROVIDER_MAX_ATTEMPTS=3
PLAN_MAX_ROUTES=3
INTERNAL_SCORING_MILES=10
DEFAULT_DISPLAY_CHECKPOINT_MILES=25
PLAN_RESULT_TTL_SECONDS=3600
WEATHER_CACHE_TTL_SECONDS=900
MAX_CHECKPOINTS_PER_ROUTE=600
MAX_CONCURRENT_PLANS_PER_SCOPE=2
FORECAST_MAX_HORIZON_HOURS=168
FORECAST_SLIDER_HOURS=48
EOF

chmod 600 "${ENV_FILE}"
echo ""
echo "Wrote secure ${ENV_FILE} (permissions 600, APP_ENV=${APP_ENV}, DATA_MODE=${DATA_MODE})."
echo ""
read -r -p "Launch Docker production stack now? [Y/n]: " LAUNCH_NOW
LAUNCH_NOW="${LAUNCH_NOW:-Y}"

if [[ "${LAUNCH_NOW}" =~ ^[Yy]$ ]]; then
  cd "${REPO_ROOT}"
  docker compose -f docker-compose.prod.yml up -d --build
  echo ""
  echo "Waiting 8 seconds for containers to initialize..."
  sleep 8
  docker compose -f docker-compose.prod.yml ps
  echo ""
  echo "Testing HTTPS readiness endpoint: https://${DOMAIN}/api/v1/health/ready"
  if curl -fsS "https://${DOMAIN}/api/v1/health/ready"; then
    echo ""
    echo "SUCCESS! Spotter is live at: https://${DOMAIN}"
  else
    echo ""
    echo "Containers started, but HTTPS check did not respond yet (DNS or Let's Encrypt cert may still be issuing)."
    echo "Check logs with: docker compose -f docker-compose.prod.yml logs -f caddy backend"
  fi
else
  echo "Skipped launch. Start anytime with:"
  echo "  docker compose -f docker-compose.prod.yml up -d --build"
fi
