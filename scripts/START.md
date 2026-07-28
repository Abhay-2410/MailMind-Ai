# MailMind AI — Local startup (Windows)

## Prerequisites

- **Docker Desktop** (recommended — runs Postgres, Redis, and the API with auto-migrations)
- Node.js 18+ for the frontend
- Google OAuth + OpenRouter API keys

## One-time setup

```powershell
cd mailmind-ai-backend
copy .env.example .env
# Edit .env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OPENROUTER_API_KEY, secrets
# Avoid unescaped $ in JWT/CSRF secrets when using Docker Compose (use $$ for a literal $)

cd ../mailmind-ai-frontend
copy .env.example .env
```

Migrations run automatically when the backend container starts (`alembic upgrade head`).

## Start (from repo root)

```powershell
# Recommended — Docker backend + Vite frontend
.\scripts\start-dev.ps1

# Or separately:
.\start-backend.ps1      # compose: postgres + redis + API on :8000
.\start-frontend.ps1     # Vite on :5173
```

Keep **`PORT=8000`** and **`BACKEND_PUBLIC_URL=http://localhost:8000`** so the Vite proxy and OAuth callback stay aligned.

## Verify

- Health: http://localhost:8000/api/v1/health
- Ready: http://localhost:8000/api/v1/health/ready (503 until DB + Redis are up)
- OAuth config: http://localhost:8000/api/v1/auth/google/oauth-config
- App: http://localhost:5173

## Google OAuth

Authorized redirect URI in Google Cloud Console:

```
http://localhost:8000/api/v1/auth/google/callback
```

Run `.\scripts\fix-google-oauth.ps1` to copy the URI and open the console.

## Required API keys

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Gmail login & sync |
| `GROQ_API_KEY` | AI assistant (default), plus any Groq model in Settings |
| `OPENROUTER_API_KEY` | Optional — OpenRouter models in Settings |

## Stop

```powershell
.\stop-backend.ps1          # stop API container + Vite
.\stop-backend.ps1 -All     # also stop postgres/redis
```
