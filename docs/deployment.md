# Deployment Guide (Render + GitHub Pages)

## 1) Backend on Render

### Option A: Blueprint via `render.yaml`

1. Push this repository to GitHub.
2. In Render: **New +** -> **Blueprint**.
3. Connect repo and select branch.
4. Render reads `render.yaml` and provisions `startdate-finder-api`.

### Option B: Manual Web Service

1. In Render: **New +** -> **Web Service**.
2. Connect GitHub repo.
3. Configure:
   - **Root Directory**: `backend`
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

### Backend env vars to set in Render

- `SODA_APP_TOKEN` = `<optional_token>`
- `WHOISXML_API_KEY` = `<optional_key>`
- `FEATURE_SOCIAL_HINTS` = `0` (or `1`)
- `MIN_PLAUSIBLE_DATE` = `1900-01-01`
- `CORS_ALLOW_ORIGINS` = `*` (initially)

After deploy, copy the service URL:

`https://startdate-finder-api.onrender.com`

## 2) Frontend on GitHub Pages

1. Edit `frontend/package.json`:
   - Set `"homepage": "https://YOUR_USERNAME.github.io/startdate-finder"`
2. Confirm `frontend/.env.production` has:
   - `VITE_API_BASE_URL=https://startdate-finder-api.onrender.com`
3. Deploy:

```bash
cd frontend
npm install
npm run deploy
```

4. In GitHub repo -> **Settings** -> **Pages**:
   - Source: `gh-pages` branch
   - Folder: `/ (root)`

Final frontend URL:

`https://YOUR_USERNAME.github.io/startdate-finder`

## 3) Tighten CORS after first successful deploy

Once frontend domain is stable, update Render env var:

`CORS_ALLOW_ORIGINS=https://YOUR_USERNAME.github.io`

Redeploy backend service.
