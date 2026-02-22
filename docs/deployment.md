# Deployment Guide

## Frontend to GitHub Pages (Static)

1. Build with backend API URL baked in:

```bash
cd frontend
VITE_API_BASE=https://your-backend.example.com npm run build
```

2. Publish `frontend/dist` to GitHub Pages (for example via `gh-pages` branch or GitHub Actions static deploy).

Example manual flow:

```bash
cd frontend
npx gh-pages -d dist
```

3. In GitHub repo settings:
- Enable Pages.
- Set source to `gh-pages` branch root.

Notes:
- Frontend is static and only needs `VITE_API_BASE`.
- Backend must allow your Pages origin via `CORS_ALLOW_ORIGINS`.

## Backend to Render

1. Create a new Web Service from your GitHub repo.
2. Runtime: Python 3.11+.
3. Build command:

```bash
pip install -r backend/requirements.txt
```

4. Start command:

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Environment variables:
- `SODA_APP_TOKEN` (recommended)
- `WHOISXML_API_KEY` (optional)
- `FEATURE_SOCIAL_HINTS` (`0` or `1`)
- `CORS_ALLOW_ORIGINS` (`https://<github-pages-domain>`)

## Backend to Fly.io (Alternative)

1. Install and login:

```bash
fly auth login
```

2. Initialize app:

```bash
fly launch --no-deploy
```

3. Set secrets:

```bash
fly secrets set SODA_APP_TOKEN=... WHOISXML_API_KEY=... FEATURE_SOCIAL_HINTS=0 CORS_ALLOW_ORIGINS=https://<github-pages-domain>
```

4. Deploy:

```bash
fly deploy
```

Use the same start command as Render:

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

