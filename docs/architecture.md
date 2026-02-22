# Architecture Notes

## Backend

- FastAPI app with asynchronous processing.
- `JobManager` orchestrates uploads, enrichment, review updates, and downloads.
- SQLite stores:
  - Job status/state (`jobs`)
  - Row-level output + review candidates (`job_rows`)
  - CT lookup cache (`ct_cache`)
  - Domain lookup cache (`domain_cache`)
  - RDAP bootstrap cache (`rdap_bootstrap_cache`)
- HTTP layer uses `httpx` + retry/backoff + concurrency semaphore.

## Enrichment Pipeline

For each row:

1. CT registry lookup + similarity scoring (`rapidfuzz`) + confidence score.
2. RDAP domain creation lookup when CT is missing/low confidence/no date.
3. WhoisXML fallback when RDAP date missing and API key is configured.
4. Optional social hint lookup (best effort, strict allowlist).
5. Date plausibility checks and final source/date selection.
6. Audit column population and review-candidate persistence.

## Frontend

- Single-page React app.
- Upload/settings panel, SSE progress, summary cards, review table, and download link.
- Typed API integration with strict TypeScript interfaces.
- Playwright e2e validates upload-to-download workflow.

