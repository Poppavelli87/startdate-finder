# StartDate Finder

StartDate Finder enriches uploaded business spreadsheets with a best-evidence business start date using:

1. Connecticut Business Registry (Socrata `n7gp-d28j`)
2. Domain creation date (RDAP)
3. WhoisXML fallback (optional)
4. Social profile hint date (optional, best effort)

## Production Targets

- Frontend: `https://YOUR_USERNAME.github.io/startdate-finder`
- Backend: `https://startdate-finder-api.onrender.com`

## Repository Layout

```text
/backend
/frontend
/scripts
/docs
/render.yaml
/docker-compose.yml
```

## Backend Environment Variables

- `SODA_APP_TOKEN` (optional, recommended)
- `WHOISXML_API_KEY` (optional)
- `FEATURE_SOCIAL_HINTS` (`0` or `1`, default `0`)
- `CORS_ALLOW_ORIGINS` (default `*`)
- `MIN_PLAUSIBLE_DATE` (default `1900-01-01`)
- `PORT` (default `8000` locally; Render injects this automatically)

The backend logs warnings when key env vars are missing and uses safe defaults.

## Local Development

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements-dev.txt
cd backend
python -m app.main
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Tests

```powershell
# backend
cd backend
pytest -q

# frontend e2e
cd ..\frontend
npx playwright install chromium
npm run test:e2e
```

## Render Deploy (Backend)

Use `render.yaml` or Render UI:

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

## GitHub Pages Deploy (Frontend)

Deployment is automatic via GitHub Actions workflow: `.github/workflows/pages.yml`.

Set these once:

- `frontend/.env.production`:
  - `VITE_API_BASE_URL=https://startdate-finder-api.onrender.com`
- `frontend/package.json`:
  - `homepage=https://poppavelli87.github.io/startdate-finder`

GitHub settings:

1. Open the repo on GitHub.
2. Go to `Settings` -> `Pages`.
3. Under `Build and deployment`, set `Source` to `GitHub Actions`.
4. Push to `main` and wait for workflow `Deploy Frontend to GitHub Pages` to finish.
5. Open `https://poppavelli87.github.io/startdate-finder/`.

If the `deploy` job fails almost immediately (for example in ~1 second), re-check:

- `Settings` -> `Pages` -> `Source` is set to `GitHub Actions`.
- `Settings` -> `Actions` -> `General` -> `Workflow permissions` allows read and write.

## CORS Notes

Current backend default allows all origins (`*`) for initial deployment.

For tighter security later, set:

```text
CORS_ALLOW_ORIGINS=https://YOUR_USERNAME.github.io
```

Then redeploy backend.
