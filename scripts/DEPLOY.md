# Deploy MailMind

## Architecture

Vercel hosts the **frontend only**. The FastAPI API + Redis run on Render; Postgres can be
Supabase (recommended) or another hosted Postgres.

```txt
Browser → Vercel (React) → Render (FastAPI + Redis) → Supabase Postgres
```

Do **not** proxy `/api` through ephemeral Cloudflare tunnels. Set `VITE_API_BASE_URL` to the
Render API so auth cookies and OAuth callbacks stay on a stable host.

Free Render web services cold-start after idle (~30–60s). The first request after sleep can be
slow; wait and retry rather than reintroducing a tunnel.

## 1. Backend on Render

1. Push this repo to GitHub (includes `render.yaml`).
2. Open [Render Blueprint](https://dashboard.render.com/select-repo?type=blueprint) and select the repo.
3. Fill sync:false env vars:

| Variable | Example |
|----------|---------|
| `APP_ENV` | `production` (set in blueprint) |
| `DATABASE_URL` | Supabase Session pooler URL (see §2b) |
| `BACKEND_PUBLIC_URL` | `https://mailmind-backend.onrender.com` |
| `FRONTEND_URL` | `https://mailmind-ai-frontend.vercel.app` |
| `CORS_ORIGINS` | `https://mailmind-ai-frontend.vercel.app,https://mailmind-ai-frontend-abhay-ms-projects.vercel.app` |
| `TOKEN_ENCRYPTION_KEY` | Fernet key from `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | From Google Cloud Console |
| `GROQ_API_KEY` | Groq key |
| `OPENROUTER_API_KEY` | Optional; needed if users pick OpenRouter models |

4. Confirm health: `GET https://YOUR-API-HOST/api/v1/health/ready` → `database` and `redis` ok.

## 2. Frontend on Vercel

```powershell
cd mailmind-ai-frontend
vercel link          # first time
vercel env add VITE_API_BASE_URL production
# value: https://YOUR-API-HOST/api/v1
vercel --prod
```

| Variable | Value |
|----------|--------|
| `VITE_API_BASE_URL` | `https://YOUR-API-HOST/api/v1` |

`vercel.json` is SPA-only (no `/api` rewrite). The browser calls Render directly with
`credentials: "include"`.

## 2b. Use Supabase for Postgres

1. Create a Supabase project.
2. Prefer the **Session pooler** (IPv4-friendly from Render):

```txt
postgresql+asyncpg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?ssl=require
```

Example region: `ap-northeast-1` → `aws-0-ap-northeast-1.pooler.supabase.com`

3. Set that as Render `DATABASE_URL`. Redis stays on Render (Blueprint keyvalue service).
4. Migrations run automatically via the backend entrypoint on deploy.

Do **not** switch this app to Supabase Auth unless you refactor the current backend-managed
Google login/session flow.

## 3. Google OAuth Console

Authorized JavaScript origins:

- `https://mailmind-ai-frontend.vercel.app`
- `https://mailmind-ai-frontend-abhay-ms-projects.vercel.app` (optional preview)
- `http://localhost:5173` (local)

Authorized redirect URIs:

- `https://YOUR-API-HOST/api/v1/auth/google/callback`  ← production (Render)
- `http://localhost:8000/api/v1/auth/google/callback`  ← local
- `http://127.0.0.1:8000/api/v1/auth/google/callback`  ← local

OAuth consent screen → **Test users** → add the Gmail accounts you use.

Helper: `.\scripts\fix-google-oauth.ps1` (reads local `.env` / compose; also prints Vercel + local URIs).

## Local vs production cookies

Production (`APP_ENV=production`) uses `SameSite=None; Secure` refresh cookies so the Vercel
origin can call the Render API with `credentials: "include"`.

## Local development

```powershell
.\scripts\start-dev.ps1
# Frontend http://localhost:5173  → Vite proxies /api → http://localhost:8000
```

Leave `VITE_API_BASE_URL` unset locally so the app uses `/api/v1` via the Vite proxy.
