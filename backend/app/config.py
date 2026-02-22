from __future__ import annotations

import os
from datetime import date
from typing import Any

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


def get_env_config() -> dict[str, Any]:
    return {
        "soda_app_token": os.getenv("SODA_APP_TOKEN", "").strip(),
        "whoisxml_api_key": os.getenv("WHOISXML_API_KEY", "").strip(),
        "feature_social_hints": bool_env("FEATURE_SOCIAL_HINTS", False),
        "enable_test_mode": bool_env("STARTDATE_TEST_MODE", False),
        "cors_allow_origins": os.getenv("CORS_ALLOW_ORIGINS", "*"),
        "min_plausible_date": os.getenv("MIN_PLAUSIBLE_DATE", "1900-01-01"),
        "db_path": os.getenv("DB_PATH", "startdate_finder.db"),
    }


def parse_min_plausible_date(raw: str) -> date:
    try:
        year, month, day = [int(v) for v in raw.split("-")]
        return date(year, month, day)
    except Exception:
        return date(1900, 1, 1)

