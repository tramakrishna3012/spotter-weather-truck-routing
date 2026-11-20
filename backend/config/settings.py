"""Django settings for Spotter weather-aware truck routing backend.

All operational endpoints, secrets, TTLs, and limits are loaded from environment
variables and validated fail-closed at startup via `validate_runtime_settings`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

# Load .env files without overriding already-set process environment variables.
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)

ALLOWED_APP_ENVS = frozenset({"development", "test", "staging", "production"})
ALLOWED_DATA_MODES = frozenset({"fixture", "live"})
SUPPORTED_DISPLAY_CHECKPOINT_MILES = frozenset({10, 25, 50})
INSECURE_SECRET_MARKERS = (
    "changeme",
    "change-me",
    "replace-me",
    "insecure",
    "dev-only",
    "spotter-dev-secret",
    "secret-key",
    "django-insecure",
)


def _env_str(name: str, default: str = "") -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean, got {raw!r}.")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be an integer, got {raw!r}."
        ) from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be a number, got {raw!r}."
        ) from exc


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def _validate_http_url(name: str, value: str, *, require_https: bool = False) -> None:
    if not value:
        raise ImproperlyConfigured(f"{name} must be configured and non-empty.")
    parsed = urlparse(value)
    allowed_schemes = {"https"} if require_https else {"http", "https"}
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise ImproperlyConfigured(
            f"{name} must be a valid {'HTTPS' if require_https else 'HTTP(S)'} URL, got {value!r}."
        )


def _is_insecure_secret(secret: str) -> bool:
    if not secret or len(secret) < 32:
        return True
    lowered = secret.lower()
    return any(marker in lowered for marker in INSECURE_SECRET_MARKERS)


# ---------------------------------------------------------------------------
# Core runtime environment
# ---------------------------------------------------------------------------
APP_ENV: str = _env_str("APP_ENV", "development").lower()
DATA_MODE: str = _env_str("DATA_MODE", "fixture" if APP_ENV in {"development", "test"} else "live").lower()
DEBUG: bool = _env_bool("DJANGO_DEBUG", APP_ENV in {"development", "test"})

_raw_secret_key = _env_str("DJANGO_SECRET_KEY", "")
if not _raw_secret_key and APP_ENV in {"development", "test"}:
    # Ephemeral non-production fallback so local dev/test boots without committing secrets.
    SECRET_KEY = "dev-only-spotter-ephemeral-local-secret-key-do-not-use-in-production"
else:
    SECRET_KEY = _raw_secret_key

FRONTEND_ORIGIN: str = _env_str("FRONTEND_ORIGIN", "http://localhost:5173")
ALLOWED_HOSTS: list[str] = _env_list(
    "ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "testserver"] if APP_ENV in {"development", "test"} else [],
)
CORS_ALLOWED_ORIGINS: list[str] = _env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    [FRONTEND_ORIGIN] if FRONTEND_ORIGIN and APP_ENV in {"development", "test"} else [],
)
CSRF_TRUSTED_ORIGINS: list[str] = _env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    CORS_ALLOWED_ORIGINS,
)

# ---------------------------------------------------------------------------
# External provider configuration (server-side only)
# ---------------------------------------------------------------------------
HERE_API_KEY: str = _env_str("HERE_API_KEY", "")
HERE_ROUTING_BASE_URL: str = _env_str("HERE_ROUTING_BASE_URL", "https://router.hereapi.com/v8")
HERE_GEOCODING_BASE_URL: str = _env_str(
    "HERE_GEOCODING_BASE_URL", "https://geocode.search.hereapi.com/v1"
)
OPEN_METEO_BASE_URL: str = _env_str("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1")
OPEN_METEO_API_KEY: str = _env_str("OPEN_METEO_API_KEY", "")

# ---------------------------------------------------------------------------
# Planning, caching, timeout, and safety limits
# ---------------------------------------------------------------------------
DATABASE_URL: str = _env_str("DATABASE_URL", "")
REDIS_URL: str = _env_str("REDIS_URL", "")

ENABLE_ASYNC_PLANNING: bool = _env_bool("ENABLE_ASYNC_PLANNING", False)
PLANNING_CONCURRENCY: int = _env_int("PLANNING_CONCURRENCY", 4)
PROVIDER_CONNECT_TIMEOUT_SECONDS: float = _env_float("PROVIDER_CONNECT_TIMEOUT_SECONDS", 5.0)
PROVIDER_READ_TIMEOUT_SECONDS: float = _env_float("PROVIDER_READ_TIMEOUT_SECONDS", 20.0)
PROVIDER_MAX_ATTEMPTS: int = _env_int("PROVIDER_MAX_ATTEMPTS", 3)

PLAN_MAX_ROUTES: int = _env_int("PLAN_MAX_ROUTES", 3)
INTERNAL_SCORING_MILES: int = _env_int("INTERNAL_SCORING_MILES", 10)
DEFAULT_DISPLAY_CHECKPOINT_MILES: int = _env_int("DEFAULT_DISPLAY_CHECKPOINT_MILES", 25)
PLAN_RESULT_TTL_SECONDS: int = _env_int("PLAN_RESULT_TTL_SECONDS", 3600)
WEATHER_CACHE_TTL_SECONDS: int = _env_int("WEATHER_CACHE_TTL_SECONDS", 900)
ROUTE_CACHE_TTL_SECONDS: int = _env_int("ROUTE_CACHE_TTL_SECONDS", 1800)
MAX_CHECKPOINTS_PER_ROUTE: int = _env_int("MAX_CHECKPOINTS_PER_ROUTE", 600)
MAX_CONCURRENT_PLANS_PER_SCOPE: int = _env_int("MAX_CONCURRENT_PLANS_PER_SCOPE", 2)
FORECAST_MAX_HORIZON_HOURS: int = _env_int("FORECAST_MAX_HORIZON_HOURS", 168)
FORECAST_SLIDER_HOURS: int = _env_int("FORECAST_SLIDER_HOURS", 48)
POLL_AFTER_SECONDS: int = _env_int("POLL_AFTER_SECONDS", 2)

ENABLE_METRICS_ENDPOINT: bool = _env_bool("ENABLE_METRICS_ENDPOINT", True)
ENABLE_RECOMMENDATIONS: bool = _env_bool("ENABLE_RECOMMENDATIONS", True)

# Session cookie & security headers
SESSION_COOKIE_NAME = "spotter_session"
SESSION_HEADER_NAME = "X-Spotter-Session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE: bool = _env_bool("SESSION_COOKIE_SECURE", APP_ENV == "production")
CSRF_COOKIE_SECURE: bool = SESSION_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"

# Throttling rates
THROTTLE_RATE_PLAN_SUBMIT: str = _env_str("THROTTLE_RATE_PLAN_SUBMIT", "60/hour")
THROTTLE_RATE_GEOCODE: str = _env_str("THROTTLE_RATE_GEOCODE", "120/min")
THROTTLE_RATE_FORECAST: str = _env_str("THROTTLE_RATE_FORECAST", "180/min")


def validate_runtime_settings(overrides: dict[str, Any] | None = None) -> None:
    """Validate all runtime settings fail-closed at startup.

    Accepts an optional dictionary of setting overrides for deterministic unit testing.
    Raises `django.core.exceptions.ImproperlyConfigured` on any invalid configuration.
    """
    cfg: dict[str, Any] = {
        "APP_ENV": APP_ENV,
        "DATA_MODE": DATA_MODE,
        "DEBUG": DEBUG,
        "SECRET_KEY": SECRET_KEY,
        "ALLOWED_HOSTS": ALLOWED_HOSTS,
        "CORS_ALLOWED_ORIGINS": CORS_ALLOWED_ORIGINS,
        "FRONTEND_ORIGIN": FRONTEND_ORIGIN,
        "HERE_API_KEY": HERE_API_KEY,
        "HERE_ROUTING_BASE_URL": HERE_ROUTING_BASE_URL,
        "HERE_GEOCODING_BASE_URL": HERE_GEOCODING_BASE_URL,
        "OPEN_METEO_BASE_URL": OPEN_METEO_BASE_URL,
        "DATABASE_URL": DATABASE_URL,
        "REDIS_URL": REDIS_URL,
        "ENABLE_ASYNC_PLANNING": ENABLE_ASYNC_PLANNING,
        "PLANNING_CONCURRENCY": PLANNING_CONCURRENCY,
        "PROVIDER_CONNECT_TIMEOUT_SECONDS": PROVIDER_CONNECT_TIMEOUT_SECONDS,
        "PROVIDER_READ_TIMEOUT_SECONDS": PROVIDER_READ_TIMEOUT_SECONDS,
        "PROVIDER_MAX_ATTEMPTS": PROVIDER_MAX_ATTEMPTS,
        "PLAN_MAX_ROUTES": PLAN_MAX_ROUTES,
        "INTERNAL_SCORING_MILES": INTERNAL_SCORING_MILES,
        "DEFAULT_DISPLAY_CHECKPOINT_MILES": DEFAULT_DISPLAY_CHECKPOINT_MILES,
        "PLAN_RESULT_TTL_SECONDS": PLAN_RESULT_TTL_SECONDS,
        "WEATHER_CACHE_TTL_SECONDS": WEATHER_CACHE_TTL_SECONDS,
        "MAX_CHECKPOINTS_PER_ROUTE": MAX_CHECKPOINTS_PER_ROUTE,
        "MAX_CONCURRENT_PLANS_PER_SCOPE": MAX_CONCURRENT_PLANS_PER_SCOPE,
        "FORECAST_MAX_HORIZON_HOURS": FORECAST_MAX_HORIZON_HOURS,
        "FORECAST_SLIDER_HOURS": FORECAST_SLIDER_HOURS,
        "SESSION_COOKIE_SECURE": SESSION_COOKIE_SECURE,
    }
    if overrides:
        cfg.update(overrides)

    app_env = str(cfg["APP_ENV"]).lower()
    data_mode = str(cfg["DATA_MODE"]).lower()
    debug = bool(cfg["DEBUG"])
    secret_key = str(cfg["SECRET_KEY"] or "")
    allowed_hosts = list(cfg["ALLOWED_HOSTS"] or [])
    cors_origins = list(cfg["CORS_ALLOWED_ORIGINS"] or [])
    frontend_origin = str(cfg["FRONTEND_ORIGIN"] or "")
    here_api_key = str(cfg["HERE_API_KEY"] or "")
    database_url = str(cfg["DATABASE_URL"] or "")
    redis_url = str(cfg["REDIS_URL"] or "")

    if app_env not in ALLOWED_APP_ENVS:
        raise ImproperlyConfigured(
            f"APP_ENV must be one of {sorted(ALLOWED_APP_ENVS)}, got {app_env!r}."
        )

    if data_mode not in ALLOWED_DATA_MODES:
        raise ImproperlyConfigured(
            f"DATA_MODE must be one of {sorted(ALLOWED_DATA_MODES)}, got {data_mode!r}."
        )

    _validate_http_url("HERE_ROUTING_BASE_URL", str(cfg["HERE_ROUTING_BASE_URL"]))
    _validate_http_url("HERE_GEOCODING_BASE_URL", str(cfg["HERE_GEOCODING_BASE_URL"]))
    _validate_http_url("OPEN_METEO_BASE_URL", str(cfg["OPEN_METEO_BASE_URL"]))

    if frontend_origin:
        _validate_http_url("FRONTEND_ORIGIN", frontend_origin)

    for origin in cors_origins:
        if origin == "*":
            raise ImproperlyConfigured("DJANGO_CORS_ALLOWED_ORIGINS must not contain wildcard '*'.")
        _validate_http_url("DJANGO_CORS_ALLOWED_ORIGINS", origin)

    # Numeric bounds validation
    if int(cfg["PLANNING_CONCURRENCY"]) < 1:
        raise ImproperlyConfigured("PLANNING_CONCURRENCY must be >= 1.")
    if float(cfg["PROVIDER_CONNECT_TIMEOUT_SECONDS"]) <= 0:
        raise ImproperlyConfigured("PROVIDER_CONNECT_TIMEOUT_SECONDS must be > 0.")
    if float(cfg["PROVIDER_READ_TIMEOUT_SECONDS"]) <= 0:
        raise ImproperlyConfigured("PROVIDER_READ_TIMEOUT_SECONDS must be > 0.")
    if int(cfg["PROVIDER_MAX_ATTEMPTS"]) < 1 or int(cfg["PROVIDER_MAX_ATTEMPTS"]) > 10:
        raise ImproperlyConfigured("PROVIDER_MAX_ATTEMPTS must be between 1 and 10.")
    if int(cfg["PLAN_MAX_ROUTES"]) < 1 or int(cfg["PLAN_MAX_ROUTES"]) > 5:
        raise ImproperlyConfigured("PLAN_MAX_ROUTES must be between 1 and 5.")
    if int(cfg["INTERNAL_SCORING_MILES"]) < 1 or int(cfg["INTERNAL_SCORING_MILES"]) > 10:
        raise ImproperlyConfigured("INTERNAL_SCORING_MILES must be between 1 and 10.")
    if int(cfg["DEFAULT_DISPLAY_CHECKPOINT_MILES"]) not in SUPPORTED_DISPLAY_CHECKPOINT_MILES:
        raise ImproperlyConfigured(
            f"DEFAULT_DISPLAY_CHECKPOINT_MILES must be one of {sorted(SUPPORTED_DISPLAY_CHECKPOINT_MILES)}."
        )
    if int(cfg["PLAN_RESULT_TTL_SECONDS"]) < 60:
        raise ImproperlyConfigured("PLAN_RESULT_TTL_SECONDS must be >= 60.")
    if int(cfg["WEATHER_CACHE_TTL_SECONDS"]) < 60:
        raise ImproperlyConfigured("WEATHER_CACHE_TTL_SECONDS must be >= 60.")
    if int(cfg["MAX_CHECKPOINTS_PER_ROUTE"]) < 2:
        raise ImproperlyConfigured("MAX_CHECKPOINTS_PER_ROUTE must be >= 2.")
    if int(cfg["MAX_CONCURRENT_PLANS_PER_SCOPE"]) < 1:
        raise ImproperlyConfigured("MAX_CONCURRENT_PLANS_PER_SCOPE must be >= 1.")
    if int(cfg["FORECAST_MAX_HORIZON_HOURS"]) < 24:
        raise ImproperlyConfigured("FORECAST_MAX_HORIZON_HOURS must be >= 24.")
    if (
        int(cfg["FORECAST_SLIDER_HOURS"]) < 1
        or int(cfg["FORECAST_SLIDER_HOURS"]) > int(cfg["FORECAST_MAX_HORIZON_HOURS"])
    ):
        raise ImproperlyConfigured(
            "FORECAST_SLIDER_HOURS must be between 1 and FORECAST_MAX_HORIZON_HOURS."
        )

    if data_mode == "live" and not here_api_key:
        raise ImproperlyConfigured("HERE_API_KEY is required when DATA_MODE='live'.")

    if bool(cfg["ENABLE_ASYNC_PLANNING"]) and not redis_url:
        raise ImproperlyConfigured("REDIS_URL is required when ENABLE_ASYNC_PLANNING=true.")

    # Production fail-closed invariants
    if app_env == "production":
        if debug:
            raise ImproperlyConfigured("DJANGO_DEBUG must be False in production.")
        if data_mode != "live":
            raise ImproperlyConfigured("DATA_MODE must be 'live' in production; fixture mode is forbidden.")
        if _is_insecure_secret(secret_key):
            raise ImproperlyConfigured(
                "DJANGO_SECRET_KEY must be set to a strong >=32-character secret in production."
            )
        if not here_api_key:
            raise ImproperlyConfigured("HERE_API_KEY must be configured in production.")
        if not allowed_hosts or "*" in allowed_hosts:
            raise ImproperlyConfigured("ALLOWED_HOSTS must list explicit hosts without '*' in production.")
        if not database_url or not database_url.startswith(("postgres://", "postgresql://")):
            raise ImproperlyConfigured(
                "DATABASE_URL must be configured with PostgreSQL in production."
            )
        if not bool(cfg["SESSION_COOKIE_SECURE"]):
            raise ImproperlyConfigured("SESSION_COOKIE_SECURE must be True in production.")


validate_runtime_settings()

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.trips.apps.TripsConfig",
]

MIDDLEWARE = [
    "config.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
if DATABASE_URL:
    DATABASES: dict[str, Any] = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Local dev/test fallback only (production rejected in validate_runtime_settings).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache & Celery
# ---------------------------------------------------------------------------
if REDIS_URL:
    CACHES: dict[str, Any] = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 3,
                "SOCKET_TIMEOUT": 3,
            },
            "KEY_PREFIX": "spotter",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "spotter-local-cache",
        }
    }

CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = not ENABLE_ASYNC_PLANNING
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_TIME_LIMIT = 120
CELERY_TASK_SOFT_TIME_LIMIT = 90
CELERY_WORKER_CONCURRENCY = PLANNING_CONCURRENCY

# ---------------------------------------------------------------------------
# CORS & Security headers
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "idempotency-key",
    "origin",
    "x-requested-with",
    "x-spotter-session",
]
CORS_EXPOSE_HEADERS = [
    "X-Request-ID",
    "X-Spotter-Session",
    "Retry-After",
]

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "strict-origin-when-cross-origin"

if APP_ENV == "production":
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = _env_int("SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0

# ---------------------------------------------------------------------------
# Internationalization & Static files
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# Django REST Framework & OpenAPI (drf-spectacular)
# ---------------------------------------------------------------------------
REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "EXCEPTION_HANDLER": "config.exceptions.structured_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.trips.throttling.PlanSubmitThrottle",
        "apps.trips.throttling.GeocodeThrottle",
        "apps.trips.throttling.ForecastThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "plan_submit": THROTTLE_RATE_PLAN_SUBMIT,
        "geocode": THROTTLE_RATE_GEOCODE,
        "forecast": THROTTLE_RATE_FORECAST,
    },
    "NON_FIELD_ERRORS_KEY": "non_field_errors",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Spotter Weather-Aware Truck Routing API",
    "DESCRIPTION": (
        "Versioned backend API for truck route planning, deterministic weather risk "
        "classification, recommendation ranking, and wall-clock forecast corridor slices."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------
LOG_LEVEL = _env_str("LOG_LEVEL", "INFO" if not DEBUG else "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "config.logging.RequestIDFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "config.logging.StructuredJsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "spotter": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
