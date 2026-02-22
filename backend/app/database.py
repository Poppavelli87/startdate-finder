from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from typing import Any

from app.utils import now_utc_iso


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress_done INTEGER NOT NULL,
                    progress_total INTEGER NOT NULL,
                    counts_json TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    settings_json TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS job_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    row_index INTEGER NOT NULL,
                    source_row_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    needs_review INTEGER NOT NULL DEFAULT 0,
                    review_candidates_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    UNIQUE(job_id, row_index)
                );
                CREATE INDEX IF NOT EXISTS idx_job_rows_job_id ON job_rows(job_id);
                CREATE INDEX IF NOT EXISTS idx_job_rows_job_review ON job_rows(job_id, needs_review);

                CREATE TABLE IF NOT EXISTS ct_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS domain_cache (
                    domain TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rdap_bootstrap_cache (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_job(self, job_id: str, settings: dict[str, Any]) -> None:
        now = now_utc_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, status, progress_done, progress_total, counts_json,
                    message, settings_json, created_at, updated_at
                ) VALUES (?, 'queued', 0, 0, ?, '', ?, ?, ?)
                """,
                (job_id, json.dumps(_default_counts()), json.dumps(settings), now, now),
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress_done: int | None = None,
        progress_total: int | None = None,
        counts: dict[str, Any] | None = None,
        message: str | None = None,
        error: str | None = None,
    ) -> None:
        updates: list[str] = []
        values: list[Any] = []
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if progress_done is not None:
            updates.append("progress_done = ?")
            values.append(progress_done)
        if progress_total is not None:
            updates.append("progress_total = ?")
            values.append(progress_total)
        if counts is not None:
            updates.append("counts_json = ?")
            values.append(json.dumps(counts))
        if message is not None:
            updates.append("message = ?")
            values.append(message)
        if error is not None:
            updates.append("error = ?")
            values.append(error)

        updates.append("updated_at = ?")
        values.append(now_utc_iso())
        values.append(job_id)

        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?", values)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return None
            return _job_row_to_dict(row)

    def get_job_settings(self, job_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT settings_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return {}
            return json.loads(row["settings_json"] or "{}")

    def upsert_job_row(
        self,
        job_id: str,
        row_index: int,
        source_row: dict[str, Any],
        result: dict[str, Any],
        needs_review: bool,
        candidates: list[dict[str, Any]],
    ) -> None:
        now = now_utc_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_rows (
                    job_id, row_index, source_row_json, result_json, needs_review,
                    review_candidates_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, row_index) DO UPDATE SET
                    source_row_json = excluded.source_row_json,
                    result_json = excluded.result_json,
                    needs_review = excluded.needs_review,
                    review_candidates_json = excluded.review_candidates_json,
                    updated_at = excluded.updated_at
                """,
                (
                    job_id,
                    row_index,
                    json.dumps(source_row),
                    json.dumps(result),
                    int(needs_review),
                    json.dumps(candidates),
                    now,
                ),
            )

    def update_job_row_result(
        self,
        job_id: str,
        row_index: int,
        result: dict[str, Any],
        needs_review: bool,
        candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        now = now_utc_iso()
        with self._connect() as conn:
            if candidates is None:
                conn.execute(
                    """
                    UPDATE job_rows
                    SET result_json = ?, needs_review = ?, updated_at = ?
                    WHERE job_id = ? AND row_index = ?
                    """,
                    (json.dumps(result), int(needs_review), now, job_id, row_index),
                )
            else:
                conn.execute(
                    """
                    UPDATE job_rows
                    SET result_json = ?, needs_review = ?, review_candidates_json = ?, updated_at = ?
                    WHERE job_id = ? AND row_index = ?
                    """,
                    (json.dumps(result), int(needs_review), json.dumps(candidates), now, job_id, row_index),
                )

    def list_job_rows(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT row_index, source_row_json, result_json, needs_review, review_candidates_json FROM job_rows WHERE job_id = ? ORDER BY row_index",
                (job_id,),
            ).fetchall()
        return [_job_result_row_to_dict(row) for row in rows]

    def list_review_rows(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT row_index, source_row_json, review_candidates_json
                FROM job_rows
                WHERE job_id = ? AND needs_review = 1
                ORDER BY row_index
                """,
                (job_id,),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            source_row = json.loads(row["source_row_json"])
            results.append(
                {
                    "row_index": row["row_index"],
                    "business": _pick(source_row, "Business"),
                    "city": _pick(source_row, "City"),
                    "zip": _pick(source_row, "Zip"),
                    "url": _pick(source_row, "URL"),
                    "candidates": json.loads(row["review_candidates_json"] or "[]"),
                }
            )
        return results

    def get_ct_cache(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json, created_at FROM ct_cache WHERE cache_key = ?", (key,)).fetchone()
            if not row:
                return None
            return {"payload": json.loads(row["payload_json"]), "created_at": row["created_at"]}

    def set_ct_cache(self, key: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ct_cache(cache_key, payload_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                (key, json.dumps(payload), now_utc_iso()),
            )

    def get_domain_cache(self, domain: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json, created_at FROM domain_cache WHERE domain = ?", (domain,)).fetchone()
            if not row:
                return None
            return {"payload": json.loads(row["payload_json"]), "created_at": row["created_at"]}

    def set_domain_cache(self, domain: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO domain_cache(domain, payload_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                (domain, json.dumps(payload), now_utc_iso()),
            )

    def get_bootstrap_cache(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json, created_at FROM rdap_bootstrap_cache WHERE id = 1").fetchone()
            if not row:
                return None
            return {"payload": json.loads(row["payload_json"]), "created_at": row["created_at"]}

    def set_bootstrap_cache(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rdap_bootstrap_cache(id, payload_json, created_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                (json.dumps(payload), now_utc_iso()),
            )

    def clear_cache(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM ct_cache")
            conn.execute("DELETE FROM domain_cache")
            conn.execute("DELETE FROM rdap_bootstrap_cache")


def _default_counts() -> dict[str, int]:
    return {
        "total_rows": 0,
        "auto_matched": 0,
        "needs_review": 0,
        "not_found": 0,
        "filled_via_domain": 0,
        "filled_via_social": 0,
    }


def _job_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    counts = json.loads(row["counts_json"] or "{}")
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "progress_done": int(row["progress_done"]),
        "progress_total": int(row["progress_total"]),
        "counts": counts or _default_counts(),
        "message": row["message"] or "",
        "settings": json.loads(row["settings_json"] or "{}"),
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _job_result_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "row_index": row["row_index"],
        "source_row": json.loads(row["source_row_json"]),
        "result": json.loads(row["result_json"]),
        "needs_review": bool(row["needs_review"]),
        "candidates": json.loads(row["review_candidates_json"] or "[]"),
    }


def _pick(source_row: dict[str, Any], key: str) -> str:
    value = source_row.get(key, "")
    return "" if value is None else str(value)

