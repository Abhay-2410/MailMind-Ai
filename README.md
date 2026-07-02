# MailMind AI

AI-powered Gmail copilot for summaries, replies, categorization, and inbox chat.

## Structure

```txt
mailmind-ai/
├── mailmind-ai-backend/    # FastAPI + PostgreSQL + Redis
├── mailmind-ai-frontend/   # React + Vite + TypeScript
├── start-backend.ps1       # Dev backend launcher
├── start-frontend.ps1      # Dev frontend launcher
└── scripts/                # Setup helpers
```

## Quick start

```powershell
# One-time: copy env templates and fill in secrets
copy mailmind-ai-backend\.env.example mailmind-ai-backend\.env
copy mailmind-ai-frontend\.env.example mailmind-ai-frontend\.env

# Terminal 1 — backend (http://localhost:8020)
.\start-backend.ps1

# Terminal 2 — frontend (http://localhost:5173)
.\start-frontend.ps1
```

Prerequisites: PostgreSQL (`mailmind` DB), Redis, Google OAuth, and OpenRouter API key. See [scripts/START.md](scripts/START.md).

## API overview

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Google OAuth, session, refresh |
| `/api/v1/inbox` | List emails, sync Gmail |
| `/api/v1/emails` | Single email detail |
| `/api/v1/ai` | Summarize, reply, categorize, assistant |
| `/api/v1/dashboard` | Stats and category analytics |
| `/api/v1/settings` | User preferences |

## Docker (database only)

```powershell
docker compose up -d postgres redis
```

Backend and frontend are run locally via the scripts above during development.
