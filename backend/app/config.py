from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

logger = logging.getLogger("startdate_finder.config")

DEFAULT_DOMAIN_DENYLIST = [
    "yelp.com",
    "angi.com",
    "homeadvisor.com",
    "bbb.org",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "google.com",
    "maps.google.com",
    "goo.gl",
    "bit.ly",
    "linktr.ee",
    "yellowpages.com",
    "mapquest.com",
    "angieslist.com",
]

CT_DATASET_URL = "https://data.ct.gov/resource/n7gp-d28j.json"
RDAP_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
HTTP_CONCURRENCY = 6
HTTP_TIMEOUT_SECONDS = 20.0
HTTP_MAX_RETRIES = 3


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _warn_if_missing(name: str, default_value: str) -> None:
    if os.getenv(name) is None:
        logger.warning("%s is not set; using default value '%s'.", name, default_value)


def get_env_config() -> dict[str, Any]:
    _warn_if_missing("SODA_APP_TOKEN", "")
    _warn_if_missing("WHOISXML_API_KEY", "")
    _warn_if_missing("FEATURE_SOCIAL_HINTS", "0")
    _warn_if_missing("CORS_ALLOW_ORIGINS", "*")
    _warn_if_missing("PORT", "8000")

    return {
        "soda_app_token": os.getenv("SODA_APP_TOKEN", "").strip(),
        "whoisxml_api_key": os.getenv("WHOISXML_API_KEY", "").strip(),
        "feature_social_hints": bool_env("FEATURE_SOCIAL_HINTS", False),
        "enable_test_mode": bool_env("STARTDATE_TEST_MODE", False),
        "cors_allow_origins": os.getenv("CORS_ALLOW_ORIGINS", "*"),
        "min_plausible_date": os.getenv("MIN_PLAUSIBLE_DATE", "1900-01-01"),
        "db_path": os.getenv("DB_PATH", "startdate_finder.db"),
    }


def get_runtime_port(default: int = 8000) -> int:
    raw = os.getenv("PORT", str(default)).strip()
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        logger.warning("Invalid PORT value '%s'; falling back to %s.", raw, default)
        return default


def parse_min_plausible_date(raw: str) -> date:
    try:
        year, month, day = [int(v) for v in raw.split("-")]
        return date(year, month, day)
    except Exception:
        return date(1900, 1, 1)
