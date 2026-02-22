from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import CACHE_TTL_SECONDS, RDAP_BOOTSTRAP_URL
from app.database import Database
from app.services.http_client import RetryHttpClient
from app.utils import extract_registrable_domain, parse_date_like


class DomainLookupService:
    def __init__(
        self,
        db: Database,
        http: RetryHttpClient,
        *,
        whoisxml_api_key: str = "",
        test_mode: bool = False,
    ) -> None:
        self._db = db
        self._http = http
        self._whoisxml_api_key = whoisxml_api_key
        self._test_mode = test_mode

    async def lookup_from_url(
        self,
        url: str,
        *,
        denylist_domains: list[str],
        enable_rdap_lookup: bool,
        enable_whois_fallback: bool,
    ) -> dict[str, Any]:
        domain = extract_registrable_domain(url)
        if not domain:
            return {
                "domain": "",
                "domain_created_date": "",
                "source": "",
                "lookup_notes": "domain_missing_or_invalid_url",
            }

        if domain.lower() in {d.lower() for d in denylist_domains}:
            return {
                "domain": domain,
                "domain_created_date": "",
                "source": "",
                "lookup_notes": "domain_on_denylist",
            }

        cached = self._db.get_domain_cache(domain)
        if cached and _is_fresh(cached["created_at"], CACHE_TTL_SECONDS):
            payload = dict(cached["payload"])
            payload.setdefault("domain", domain)
            payload.setdefault("lookup_notes", "domain_cache_hit")
            return payload

        if self._test_mode:
            payload = self._fake_lookup(domain)
            self._db.set_domain_cache(domain, payload)
            return payload

        rdap_result = {
            "domain": domain,
            "domain_created_date": "",
            "source": "",
            "lookup_notes": "",
        }
        notes: list[str] = []
        if enable_rdap_lookup:
            rdap_result = await self._lookup_rdap(domain)
            notes.append(rdap_result.get("lookup_notes", ""))
            if rdap_result.get("domain_created_date"):
                rdap_result["lookup_notes"] = "; ".join([n for n in notes if n])
                self._db.set_domain_cache(domain, rdap_result)
                return rdap_result
        else:
            notes.append("rdap_disabled")

        if enable_whois_fallback and self._whoisxml_api_key:
            whois_result = await self._lookup_whoisxml(domain)
            notes.append(whois_result.get("lookup_notes", ""))
            whois_result["lookup_notes"] = "; ".join([n for n in notes if n])
            self._db.set_domain_cache(domain, whois_result)
            return whois_result

        if enable_whois_fallback and not self._whoisxml_api_key:
            notes.append("whoisxml_key_missing")
        elif not enable_whois_fallback:
            notes.append("whoisxml_disabled")

        final = {
            "domain": domain,
            "domain_created_date": "",
            "source": "",
            "lookup_notes": "; ".join([n for n in notes if n]) or "domain_date_not_found",
        }
        self._db.set_domain_cache(domain, final)
        return final

    async def _lookup_rdap(self, domain: str) -> dict[str, Any]:
        try:
            bootstrap = await self._load_bootstrap()
            server_url = _find_rdap_server(bootstrap, domain)
            if not server_url:
                return {
                    "domain": domain,
                    "domain_created_date": "",
                    "source": "",
                    "lookup_notes": "rdap_server_not_found",
                }
            url = f"{server_url.rstrip('/')}/domain/{domain}"
            payload = await self._http.get_json(url, headers={"Accept": "application/rdap+json"})
            created = parse_rdap_created_date(payload)
            return {
                "domain": domain,
                "domain_created_date": created,
                "source": "domain_rdap" if created else "",
                "lookup_notes": "rdap_created_date_found" if created else "rdap_created_date_missing",
            }
        except Exception as exc:
            return {
                "domain": domain,
                "domain_created_date": "",
                "source": "",
                "lookup_notes": f"rdap_lookup_failed={exc.__class__.__name__}",
            }

    async def _lookup_whoisxml(self, domain: str) -> dict[str, Any]:
        endpoint = "https://www.whoisxmlapi.com/whoisserver/WhoisService"
        params = {
            "apiKey": self._whoisxml_api_key,
            "domainName": domain,
            "outputFormat": "JSON",
        }
        try:
            payload = await self._http.get_json(endpoint, params=params)
            created_raw = (
                payload.get("WhoisRecord", {}).get("createdDateNormalized")
                or payload.get("WhoisRecord", {}).get("createdDate")
                or payload.get("WhoisRecord", {}).get("registryData", {}).get("createdDate")
                or payload.get("createdDate")
                or ""
            )
            parsed = parse_date_like(created_raw)
            return {
                "domain": domain,
                "domain_created_date": parsed.isoformat() if parsed else "",
                "source": "whoisxml" if parsed else "",
                "lookup_notes": "whoisxml_created_date_found" if parsed else "whoisxml_created_date_missing",
            }
        except Exception as exc:
            return {
                "domain": domain,
                "domain_created_date": "",
                "source": "",
                "lookup_notes": f"whoisxml_failed={exc.__class__.__name__}",
            }

    async def _load_bootstrap(self) -> dict[str, Any]:
        cached = self._db.get_bootstrap_cache()
        if cached and _is_fresh(cached["created_at"], CACHE_TTL_SECONDS):
            return cached["payload"]
        payload = await self._http.get_json(RDAP_BOOTSTRAP_URL, headers={"Accept": "application/json"})
        if not isinstance(payload, dict):
            raise ValueError("Unexpected RDAP bootstrap response")
        self._db.set_bootstrap_cache(payload)
        return payload

    def _fake_lookup(self, domain: str) -> dict[str, Any]:
        if domain == "acmeplumbing.com":
            return {
                "domain": domain,
                "domain_created_date": "2014-05-01",
                "source": "domain_rdap",
                "lookup_notes": "domain_test_mode=1",
            }
        return {
            "domain": domain,
            "domain_created_date": "",
            "source": "",
            "lookup_notes": "domain_test_mode=1; domain_date_not_found",
        }


def parse_rdap_created_date(payload: dict[str, Any]) -> str:
    events = payload.get("events", [])
    created_candidates = []
    for event in events:
        action = str(event.get("eventAction", "")).strip().lower()
        if action in {"registration", "created", "creation"}:
            parsed = parse_date_like(event.get("eventDate"))
            if parsed:
                created_candidates.append(parsed)
    if not created_candidates:
        return ""
    return min(created_candidates).isoformat()


def _find_rdap_server(bootstrap_payload: dict[str, Any], domain: str) -> str:
    tld = domain.rsplit(".", 1)[-1].lower()
    services = bootstrap_payload.get("services", [])
    for service in services:
        if not isinstance(service, list) or len(service) < 2:
            continue
        tlds, urls = service[0], service[1]
        if not isinstance(tlds, list) or not isinstance(urls, list):
            continue
        if tld in {str(v).lower() for v in tlds} and urls:
            return str(urls[0])
    return ""


def _is_fresh(created_at_iso: str, ttl_seconds: int) -> bool:
    try:
        created_at = datetime.fromisoformat(created_at_iso)
    except Exception:
        return False
    return (datetime.now(tz=created_at.tzinfo) - created_at).total_seconds() <= ttl_seconds

