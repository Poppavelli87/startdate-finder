from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.http_client import RetryHttpClient
from app.utils import parse_date_like

SOCIAL_ALLOWLIST_PATTERNS = [
    re.compile(r"^facebook\.com/[^/?#]+/?$", re.IGNORECASE),
    re.compile(r"^instagram\.com/[^/?#]+/?$", re.IGNORECASE),
    re.compile(r"^(x\.com|twitter\.com)/[^/?#]+/?$", re.IGNORECASE),
    re.compile(r"^linkedin\.com/company/[^/?#]+/?$", re.IGNORECASE),
]


class SocialHintService:
    def __init__(self, http: RetryHttpClient, *, test_mode: bool = False) -> None:
        self._http = http
        self._test_mode = test_mode

    async def lookup(self, url: str) -> dict[str, Any]:
        if not url:
            return _empty(notes="social_url_missing")

        normalized = _normalize_url(url)
        if not normalized:
            return _empty(notes="social_url_invalid")

        if not _is_allowed_profile(normalized):
            return _empty(notes="social_url_not_allowlisted")

        if self._test_mode:
            return {
                "social_profile_url": normalized,
                "social_created_hint_date": "",
                "social_lookup_notes": "social_test_mode=1; not_available",
                "confidence": 0.6,
            }

        try:
            payload = await self._http.get_json(normalized, headers={"User-Agent": "StartDateFinder/1.0"})
            # get_json may fail on HTML pages; fallback with raw request.
            text = str(payload)
        except Exception:
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    response = await client.get(
                        normalized,
                        headers={"User-Agent": "StartDateFinder/1.0"},
                    )
                    response.raise_for_status()
                    text = response.text
            except Exception as exc:
                return {
                    "social_profile_url": normalized,
                    "social_created_hint_date": "",
                    "social_lookup_notes": f"social_fetch_failed={exc.__class__.__name__}",
                    "confidence": 0.6,
                }

        parsed = _extract_date_from_html(text)
        if not parsed:
            return {
                "social_profile_url": normalized,
                "social_created_hint_date": "",
                "social_lookup_notes": "social_created_date_not_available",
                "confidence": 0.6,
            }
        return {
            "social_profile_url": normalized,
            "social_created_hint_date": parsed,
            "social_lookup_notes": "social_created_date_extracted_public_hint",
            "confidence": 0.6,
        }


def _normalize_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = (parsed.netloc or parsed.path).lower()
    path = parsed.path if parsed.netloc else ""
    if not path:
        path = "/"
    if host.startswith("www."):
        host = host[4:]
    return f"https://{host}{path}".rstrip("/")


def _is_allowed_profile(normalized_url: str) -> bool:
    parsed = urlparse(normalized_url)
    candidate = f"{parsed.netloc}{parsed.path}".strip("/")
    for pattern in SOCIAL_ALLOWLIST_PATTERNS:
        if pattern.match(candidate):
            return True
    return False


def _extract_date_from_html(text: str) -> str:
    patterns = [
        re.compile(r'"created_at"\s*:\s*"([^"]+)"', re.IGNORECASE),
        re.compile(r'"foundingDate"\s*:\s*"([^"]+)"', re.IGNORECASE),
        re.compile(r'"startDate"\s*:\s*"([^"]+)"', re.IGNORECASE),
        re.compile(r'"memberSince"\s*:\s*"([^"]+)"', re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        parsed = parse_date_like(match.group(1))
        if parsed:
            return parsed.isoformat()
    return ""


def _empty(notes: str) -> dict[str, Any]:
    return {
        "social_profile_url": "",
        "social_created_hint_date": "",
        "social_lookup_notes": notes,
        "confidence": 0.0,
    }

