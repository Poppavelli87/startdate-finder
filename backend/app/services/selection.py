from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.schemas import JobSettings
from app.utils import is_future, parse_date_like


@dataclass
class SelectionCandidate:
    source: str
    date_value: date
    confidence: float


def choose_start_date(
    ct_result: dict[str, Any],
    domain_result: dict[str, Any],
    social_result: dict[str, Any],
    settings: JobSettings,
) -> dict[str, Any]:
    min_date = parse_date_like(settings.min_plausible_date) or date(1900, 1, 1)
    notes = {
        "ct_query_notes": ct_result.get("query_notes", "") or "",
        "domain_lookup_notes": domain_result.get("lookup_notes", "") or "",
        "social_lookup_notes": social_result.get("social_lookup_notes", "") or "",
    }

    ct_date = _plausible_date(
        ct_result.get("registration_date", ""),
        min_date=min_date,
        note_key="ct_query_notes",
        notes=notes,
        source_label="ct_date",
    )
    domain_date = _plausible_date(
        domain_result.get("domain_created_date", ""),
        min_date=min_date,
        note_key="domain_lookup_notes",
        notes=notes,
        source_label="domain_date",
    )
    social_date = _plausible_date(
        social_result.get("social_created_hint_date", ""),
        min_date=min_date,
        note_key="social_lookup_notes",
        notes=notes,
        source_label="social_date",
    )

    candidates: list[SelectionCandidate] = []
    if ct_date:
        candidates.append(
            SelectionCandidate(
                source="ct_registry",
                date_value=ct_date,
                confidence=float(ct_result.get("confidence") or 0.0),
            )
        )
    if domain_date:
        source = domain_result.get("source") or "domain_rdap"
        confidence = 0.75 if source == "domain_rdap" else 0.70
        candidates.append(
            SelectionCandidate(
                source=source,
                date_value=domain_date,
                confidence=confidence,
            )
        )
    if social_date:
        candidates.append(
            SelectionCandidate(
                source="social_hint",
                date_value=social_date,
                confidence=min(0.60, float(social_result.get("confidence") or 0.60)),
            )
        )

    chosen_source = "not_found"
    chosen_date: date | None = None
    chosen_confidence = 0.0

    if settings.prefer_earliest_known_date and candidates:
        chosen = min(candidates, key=lambda c: c.date_value)
        chosen_source = chosen.source
        chosen_date = chosen.date_value
        chosen_confidence = chosen.confidence
    else:
        ct_conf = float(ct_result.get("confidence") or 0.0)
        if ct_date and ct_conf >= settings.high_confidence_threshold:
            chosen_source = "ct_registry"
            chosen_date = ct_date
            chosen_confidence = ct_conf
        elif domain_date:
            chosen_source = (domain_result.get("source") or "domain_rdap").strip() or "domain_rdap"
            chosen_date = domain_date
            chosen_confidence = 0.75 if chosen_source == "domain_rdap" else 0.70
        elif social_date:
            chosen_source = "social_hint"
            chosen_date = social_date
            chosen_confidence = min(0.60, float(social_result.get("confidence") or 0.60))

    return {
        "chosen_start_date": chosen_date.isoformat() if chosen_date else "",
        "chosen_source": chosen_source,
        "confidence": round(chosen_confidence, 2),
        "ct_query_notes": notes["ct_query_notes"].strip("; "),
        "domain_lookup_notes": notes["domain_lookup_notes"].strip("; "),
        "social_lookup_notes": notes["social_lookup_notes"].strip("; "),
    }


def _plausible_date(
    raw_value: str,
    *,
    min_date: date,
    note_key: str,
    notes: dict[str, str],
    source_label: str,
) -> date | None:
    parsed = parse_date_like(raw_value)
    if not parsed:
        return None
    if parsed < min_date:
        notes[note_key] = _append_note(notes[note_key], f"{source_label}_rejected_before_min_date")
        return None
    if is_future(parsed):
        notes[note_key] = _append_note(notes[note_key], f"{source_label}_rejected_future_date")
        return None
    return parsed


def _append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    return f"{existing}; {note}"

