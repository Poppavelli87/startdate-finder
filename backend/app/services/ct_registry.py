from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.config import CACHE_TTL_SECONDS, CT_DATASET_URL
from app.database import Database
from app.services.http_client import RetryHttpClient
from app.utils import (
    compute_ct_confidence,
    normalize_business_name,
    normalize_city,
    normalize_zip,
    parse_date_like,
    token_similarity,
)

FIELD_CANDIDATES = {
    "name": [
        "business_name",
        "businessname",
        "entity_name",
        "business",
        "name",
    ],
    "city": [
        "city",
        "principal_city",
        "principal_town",
        "town",
        "mailing_city",
    ],
    "zip": [
        "zip",
        "zip_code",
        "zipcode",
        "mailing_zip",
    ],
    "registration_date": [
        "date_registration",
        "date_registered",
        "date_formation",
        "formation_date",
        "registration_date",
        "date_established",
    ],
    "entity_id": [
        "business_id",
        "entity_id",
        "record_id",
        "number",
        "id",
    ],
}


@dataclass
class CTCandidate:
    name: str
    city: str
    zip: str
    entity_id: str
    registration_date_raw: str
    registration_date: str
    similarity: float
    confidence: float
    city_match: bool
    zip_match: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "city": self.city,
            "zip": self.zip,
            "entity_id": self.entity_id,
            "registration_date_raw": self.registration_date_raw,
            "registration_date": self.registration_date,
            "similarity": round(self.similarity, 2),
            "confidence": round(self.confidence, 2),
        }


class CTRegistryService:
    def __init__(
        self,
        db: Database,
        http: RetryHttpClient,
        *,
        soda_app_token: str = "",
        test_mode: bool = False,
        field_overrides: dict[str, str] | None = None,
    ) -> None:
        self._db = db
        self._http = http
        self._soda_app_token = soda_app_token
        self._test_mode = test_mode
        self._field_overrides = field_overrides or {}

    async def lookup(self, business_name: str, city: str, zip_code: str) -> dict[str, Any]:
        normalized_name = normalize_business_name(business_name)
        normalized_city = normalize_city(city)
        normalized_zip = normalize_zip(zip_code)
        cache_key = f"{normalized_name}|{normalized_city}|{normalized_zip}"

        cached = self._db.get_ct_cache(cache_key)
        if cached and _is_fresh(cached["created_at"], CACHE_TTL_SECONDS):
            return cached["payload"]

        if self._test_mode:
            payload = self._fake_lookup(business_name, city, zip_code)
            self._db.set_ct_cache(cache_key, payload)
            return payload

        payload = await self._remote_lookup(business_name, city, zip_code)
        self._db.set_ct_cache(cache_key, payload)
        return payload

    async def _remote_lookup(self, business_name: str, city: str, zip_code: str) -> dict[str, Any]:
        normalized_target = normalize_business_name(business_name)
        norm_city = normalize_city(city)
        norm_zip = normalize_zip(zip_code)
        headers = {"Accept": "application/json"}
        if self._soda_app_token:
            headers["X-App-Token"] = self._soda_app_token

        params: dict[str, Any] = {"$limit": 60}
        tokens = [t for t in normalized_target.split() if t]
        if tokens:
            params["$q"] = " ".join(tokens)

        notes: list[str] = []
        records: list[dict[str, Any]] = []
        try:
            raw = await self._http.get_json(CT_DATASET_URL, params=params, headers=headers)
            if isinstance(raw, list):
                records = [r for r in raw if isinstance(r, dict)]
            notes.append(f"ct_query_limit={params['$limit']}")
            if params.get("$q"):
                notes.append("ct_query_mode=full_text")
        except Exception as exc:
            notes.append(f"ct_query_failed={exc.__class__.__name__}")
            return _empty_result(notes="; ".join(notes))

        if not records:
            notes.append("ct_no_records")
            return _empty_result(notes="; ".join(notes))

        field_map = self._resolve_field_map(records)
        notes.append(
            "ct_field_map="
            + ",".join([f"{k}:{v or 'n/a'}" for k, v in field_map.items()])
        )

        candidates: list[CTCandidate] = []
        for record in records:
            candidate_name = str(record.get(field_map["name"], "")).strip()
            if not candidate_name:
                continue
            similarity = token_similarity(normalized_target, normalize_business_name(candidate_name))
            candidate_city = str(record.get(field_map["city"], "")).strip()
            candidate_zip = str(record.get(field_map["zip"], "")).strip()
            city_match = bool(norm_city and normalize_city(candidate_city) == norm_city)
            zip_match = bool(norm_zip and normalize_zip(candidate_zip) == norm_zip)
            confidence = compute_ct_confidence(similarity, city_match=city_match, zip_match=zip_match)
            raw_date = str(record.get(field_map["registration_date"], "")).strip()
            parsed_date = parse_date_like(raw_date)
            entity_id = str(record.get(field_map["entity_id"], "")).strip()
            candidates.append(
                CTCandidate(
                    name=candidate_name,
                    city=candidate_city,
                    zip=normalize_zip(candidate_zip) or candidate_zip,
                    entity_id=entity_id,
                    registration_date_raw=raw_date,
                    registration_date=parsed_date.isoformat() if parsed_date else "",
                    similarity=similarity,
                    confidence=confidence,
                    city_match=city_match,
                    zip_match=zip_match,
                )
            )

        if not candidates:
            notes.append("ct_no_name_candidates")
            return _empty_result(notes="; ".join(notes))

        sorted_candidates = sorted(
            candidates,
            key=lambda c: (c.similarity, c.city_match or c.zip_match, c.confidence),
            reverse=True,
        )
        top = sorted_candidates[0]
        needs_review = _is_ambiguous(sorted_candidates, norm_city)
        top5 = [c.to_dict() for c in sorted_candidates[:5]]
        notes.append(f"ct_candidates={len(sorted_candidates)}")
        if needs_review:
            notes.append("ct_needs_review=1")

        return {
            "matched_name": top.name,
            "entity_id": top.entity_id,
            "registration_date_raw": top.registration_date_raw,
            "registration_date": top.registration_date,
            "confidence": round(top.confidence, 2),
            "similarity": round(top.similarity, 2),
            "query_notes": "; ".join(notes),
            "needs_review": needs_review,
            "candidates": top5,
        }

    def _resolve_field_map(self, records: list[dict[str, Any]]) -> dict[str, str]:
        if not records:
            return {key: "" for key in FIELD_CANDIDATES}
        existing = {key.lower(): key for key in records[0].keys()}
        resolved: dict[str, str] = {}
        for semantic, candidates in FIELD_CANDIDATES.items():
            override = self._field_overrides.get(semantic, "").strip()
            if override:
                resolved[semantic] = override
                continue
            chosen = ""
            for candidate in candidates:
                if candidate.lower() in existing:
                    chosen = existing[candidate.lower()]
                    break
            if not chosen and semantic in {"name", "registration_date"}:
                # Best-effort fallback so schema drift doesn't hard-fail.
                for key in existing.values():
                    key_lower = key.lower()
                    if semantic == "name" and "name" in key_lower:
                        chosen = key
                        break
                    if semantic == "registration_date" and "date" in key_lower:
                        chosen = key
                        break
            resolved[semantic] = chosen
        return resolved

    def _fake_lookup(self, business_name: str, city: str, zip_code: str) -> dict[str, Any]:
        normalized = normalize_business_name(business_name)
        city_norm = normalize_city(city)
        zip_norm = normalize_zip(zip_code)
        if "ACME" in normalized:
            city_match = city_norm in {"HARTFORD", ""}
            zip_match = zip_norm in {"06103", ""}
            confidence = compute_ct_confidence(99.0, city_match=city_match, zip_match=zip_match)
            return {
                "matched_name": "ACME PLUMBING LLC",
                "entity_id": "CT-TEST-001",
                "registration_date_raw": "2013-04-22T00:00:00.000",
                "registration_date": "2013-04-22",
                "confidence": confidence,
                "similarity": 99.0,
                "query_notes": "ct_test_mode=1; ct_candidates=1",
                "needs_review": False,
                "candidates": [
                    {
                        "name": "ACME PLUMBING LLC",
                        "city": "Hartford",
                        "zip": "06103",
                        "entity_id": "CT-TEST-001",
                        "registration_date_raw": "2013-04-22T00:00:00.000",
                        "registration_date": "2013-04-22",
                        "similarity": 99.0,
                        "confidence": round(confidence, 2),
                    }
                ],
            }

        if "SMITH" in normalized:
            return {
                "matched_name": "SMITH SERVICES LLC",
                "entity_id": "CT-TEST-010",
                "registration_date_raw": "2018-08-10",
                "registration_date": "2018-08-10",
                "confidence": 0.8,
                "similarity": 93.0,
                "query_notes": "ct_test_mode=1; ct_candidates=2; ct_needs_review=1",
                "needs_review": True,
                "candidates": [
                    {
                        "name": "SMITH SERVICES LLC",
                        "city": "New Haven",
                        "zip": "06510",
                        "entity_id": "CT-TEST-010",
                        "registration_date_raw": "2018-08-10",
                        "registration_date": "2018-08-10",
                        "similarity": 93.0,
                        "confidence": 0.8,
                    },
                    {
                        "name": "SMITH SERVICE GROUP LLC",
                        "city": "New Haven",
                        "zip": "06510",
                        "entity_id": "CT-TEST-011",
                        "registration_date_raw": "2019-02-12",
                        "registration_date": "2019-02-12",
                        "similarity": 92.0,
                        "confidence": 0.8,
                    },
                ],
            }

        return _empty_result(notes="ct_test_mode=1; ct_no_records")


def _is_ambiguous(candidates: list[CTCandidate], normalized_city: str) -> bool:
    if len(candidates) < 2:
        return False
    first, second = candidates[0], candidates[1]
    if abs(first.similarity - second.similarity) <= 2.0:
        return True
    if normalized_city:
        plausible_city_matches = [
            c for c in candidates[:5] if normalize_city(c.city) == normalized_city and c.similarity >= 90
        ]
        if len(plausible_city_matches) > 1:
            return True
    return False


def _empty_result(notes: str = "") -> dict[str, Any]:
    return {
        "matched_name": "",
        "entity_id": "",
        "registration_date_raw": "",
        "registration_date": "",
        "confidence": 0.0,
        "similarity": 0.0,
        "query_notes": notes,
        "needs_review": False,
        "candidates": [],
    }


def _is_fresh(created_at_iso: str, ttl_seconds: int) -> bool:
    try:
        created_at = datetime.fromisoformat(created_at_iso)
    except Exception:
        return False
    return (datetime.now(tz=created_at.tzinfo) - created_at).total_seconds() <= ttl_seconds

