from __future__ import annotations

import re
import string
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

from dateutil import parser as date_parser
from publicsuffix2 import get_sld
from rapidfuzz import fuzz

SUFFIX_TOKENS = {
    "LLC",
    "L.L.C",
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "LTD",
    "LIMITED",
    "PLLC",
    "PC",
    "LLP",
}


def now_utc_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def normalize_business_name(name: str | None) -> str:
    if not name:
        return ""
    upper = name.upper()
    no_punct = upper.translate(str.maketrans("", "", string.punctuation))
    tokens = [tok for tok in no_punct.split() if tok and tok not in SUFFIX_TOKENS]
    collapsed = re.sub(r"\s+", " ", " ".join(tokens)).strip()
    return collapsed


def normalize_city(value: str | None) -> str:
    if not value:
        return ""
    upper = value.upper().strip()
    upper = re.sub(r"[^A-Z0-9\s]", "", upper)
    return re.sub(r"\s+", " ", upper).strip()


def normalize_zip(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"[^0-9]", "", str(value))
    return digits[:5]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def parse_date_like(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date_parser.parse(raw).date()
    except Exception:
        return None


def iso_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def token_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return float(fuzz.token_set_ratio(left, right))


def compute_ct_confidence(similarity: float, city_match: bool, zip_match: bool) -> float:
    has_location_hint = city_match or zip_match
    if similarity >= 97 and has_location_hint:
        return 0.95
    if similarity >= 95 and has_location_hint:
        return 0.90
    if similarity >= 92:
        return 0.80
    return round(max(0.2, similarity / 140.0), 2)


def is_future(value: date) -> bool:
    return value > datetime.now(tz=UTC).date()


def extract_registrable_domain(url: str | None) -> str:
    if not url:
        return ""
    raw = url.strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return ""
    domain = get_sld(host, strict=False) or host
    return domain.lower()

