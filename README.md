# MailMind AI

AI-powered Gmail copilot for summaries, replies, categorization, and inbox chat.

## Structure

```txt
mailmind-ai/
├── mailmind-ai-backend/    # FastAPI + PostgreSQL + Redis
├── mailmind-ai-frontend/   # React + Vite + TypeScript
├── docker-compose.yml      # Postgres + Redis + backend (local)
├── render.yaml             # Render Blueprint (API + Redis)
├── start-backend.ps1
├── start-frontend.ps1
├── stop-backend.ps1
└── scripts/                # start-dev, OAuth helper, DEPLOY.md
```

## Production

- **Frontend:** [Vercel](https://mailmind-ai-frontend.vercel.app) with `VITE_API_BASE_URL=https://YOUR-API.onrender.com/api/v1`
- **API + Redis:** [Render Blueprint](render.yaml) — see [scripts/DEPLOY.md](scripts/DEPLOY.md)
- **Database:** Supabase Session pooler (recommended)

Google OAuth production redirect URI is the **Render** callback:

`https://YOUR-API.onrender.com/api/v1/auth/google/callback`

Helper: `.\scripts\prepare-render-deploy.ps1`

## Quick start (local)

Requires **Docker Desktop**. Backend runs migrations automatically on container start.

```powershell
# One-time: copy env templates and fill in secrets
copy mailmind-ai-backend\.env.example mailmind-ai-backend\.env
# Avoid unescaped $ characters in JWT/CSRF secrets (or write $$ for a literal $)

# Option A — one script (opens frontend; starts compose backend)
.\scripts\start-dev.ps1

# Option B — two terminals
.\start-backend.ps1      # postgres + redis + API on :8000
.\start-frontend.ps1     # Vite on :5173
```

- **Frontend:** http://localhost:5173  
- **API / docs:** http://localhost:8000 / http://localhost:8000/docs  
- **Google OAuth redirect URI:** `http://localhost:8000/api/v1/auth/google/callback`

Stop app processes:

```powershell
.\stop-backend.ps1          # stop backend container + Vite
.\stop-backend.ps1 -All     # also stop postgres/redis
```

Also configure Google OAuth and Groq/OpenRouter API keys. See [scripts/START.md](scripts/START.md) and [scripts/DEPLOY.md](scripts/DEPLOY.md).

## API overview

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Google OAuth, session, refresh, Gmail reconnect |
| `/api/v1/inbox` | List emails, sync Gmail |
| `/api/v1/emails` | Single email detail |
| `/api/v1/search` | Natural-language Gmail search |
| `/api/v1/ai` | Summarize, reply, categorize, assistant |
| `/api/v1/dashboard` | Stats and category analytics |
| `/api/v1/cleanup` | Smart Cleanup + inbox triage |
| `/api/v1/settings` | User preferences |

## Docker notes

`docker compose up -d --build` starts postgres, redis, and the API. The backend **entrypoint runs `alembic upgrade head`** before uvicorn so fresh volumes get a schema automatically.
