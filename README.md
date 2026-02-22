# StartDate Finder

StartDate Finder enriches uploaded business spreadsheets with a best-evidence business start date using this priority chain:

1. Connecticut Business Registry (Socrata dataset `n7gp-d28j`)
2. Domain creation date from RDAP
3. WhoisXML API fallback (optional)
4. Public social profile hint date (optional, best effort, off by default)

The app includes caching, confidence scoring, ambiguity review UI, audit columns, SSE progress updates, Docker packaging, backend tests, frontend e2e tests, and CI.

## Repository Layout

```text
/backend      FastAPI API + enrichment engine + SQLite cache/state + pytest
/frontend     React + Vite + TypeScript UI + Playwright e2e
/scripts      Utility scripts (fixture generation)
/docs         Deployment/architecture docs
/docker-compose.yml
/Dockerfile
```

## Environment Variables

- `SODA_APP_TOKEN` (optional, recommended) - Socrata app token.
- `WHOISXML_API_KEY` (optional) - enables WhoisXML fallback.
- `FEATURE_SOCIAL_HINTS` (optional, default `0`) - enables social hint toggle in UI.
- `CORS_ALLOW_ORIGINS` (optional, default `*`) - comma-separated origins.
- `MIN_PLAUSIBLE_DATE` (optional, default `1900-01-01`) - global lower date bound.
- `STARTDATE_TEST_MODE` (optional, default `0`) - deterministic fake provider responses for tests.

## Local Development

From repo root (`startdate-finder`):

1. Backend setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

2. Frontend setup:

```powershell
cd frontend
npm install
cd ..
```

3. Create the fixture spreadsheet used by tests:

```powershell
python scripts/create_fixture_xlsx.py
```

4. Run backend:

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Run frontend (new terminal):

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`.

## Docker

```powershell
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

## Testing

1. Backend unit tests:

```powershell
cd backend
pytest -q
```

2. Playwright e2e:

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

The Playwright config starts backend + frontend automatically and uses `STARTDATE_TEST_MODE=1`.

## API Endpoints

- `POST /api/jobs` (multipart: `file`, `settings_json`)
- `GET /api/jobs/{job_id}/status`
- `GET /api/jobs/{job_id}/events` (SSE)
- `GET /api/jobs/{job_id}/review`
- `POST /api/jobs/{job_id}/review`
- `GET /api/jobs/{job_id}/download`
- `POST /api/cache/clear`

## Spreadsheet Output

The app fills existing `Date Established` and appends these audit columns:

- `chosen_start_date`
- `chosen_source`
- `confidence`
- `ct_matched_name`
- `ct_entity_id`
- `ct_registration_date_raw`
- `ct_query_notes`
- `domain`
- `domain_created_date`
- `domain_lookup_notes`
- `social_profile_url`
- `social_created_hint_date`
- `social_lookup_notes`

## Deploy

See `docs/deployment.md` for exact GitHub Pages + Render/Fly deployment steps.

