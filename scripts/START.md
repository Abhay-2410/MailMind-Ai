# MailMind AI — Local startup (Windows)

## Prerequisites

- Python 3.11+ with backend venv at `mailmind-ai-backend/.venv`
- Node.js 18+ for the frontend
- PostgreSQL 16+ (database: `mailmind`, user: `mailmind`, password: `mailmind`)
- Redis on port 6379

## One-time setup

```powershell
# Backend
cd mailmind-ai-backend
copy .env.example .env
# Edit .env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OPENROUTER_API_KEY, secrets

# Frontend
cd ../mailmind-ai-frontend
copy .env.example .env

# Database migrations
cd ../mailmind-ai-backend
.\.venv\Scripts\alembic upgrade head
```

## Start (from repo root)

```powershell
# Terminal 1 — backend (http://localhost:8000)
.\start-backend.ps1

# Terminal 2 — frontend (http://localhost:5173)
.\start-frontend.ps1
```

Or start both in separate windows:

```powershell
.\scripts\start-dev.ps1
```

## Verify

- Health: http://localhost:8000/api/v1/health
- Ready: http://localhost:8000/api/v1/health/ready
- OAuth config (dev): http://localhost:8000/api/v1/auth/google/oauth-config
- App: http://localhost:5173

## Google OAuth

Set in `mailmind-ai-backend/.env`:

- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` from Google Cloud Console
- `BACKEND_PUBLIC_URL=http://localhost:8000` (must match `PORT` in `.env`)

Authorized redirect URI in Google Cloud Console:

```
http://localhost:8000/api/v1/auth/google/callback
```

Run `.\scripts\fix-google-oauth.ps1` to copy the URI and open the console.

## Required API keys

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Gmail login & sync |
| `OPENROUTER_API_KEY` | AI summarize, reply, search, assistant, categorization |

Without these, the UI loads but login and AI features will fail.

## Stop

```powershell
.\stop-backend.ps1
```

Stops backend (port 8000) and frontend (port 5173).
