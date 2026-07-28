# Deploy MailMind

## Architecture

Vercel hosts the **frontend only**. The FastAPI API + Postgres + Redis cannot run on Vercel
(they need long-running containers). Deploy the API on Render (or Railway/Fly), then point
the Vercel app at that API URL.

```txt
Browser → Vercel (React) → Render/Railway (FastAPI + Postgres + Redis)
```

## 1. Frontend on Vercel

From repo root (or the frontend folder):

```powershell
cd mailmind-ai-frontend
vercel link          # first time: create/link project, Root Directory = mailmind-ai-frontend if linking from monorepo
vercel --prod
```

After the API is live, set this env in the Vercel project and redeploy:

| Variable | Value |
|----------|--------|
| `VITE_API_BASE_URL` | `https://YOUR-API-HOST/api/v1` |

## 2. Backend on Render

1. Push this repo to GitHub (includes `render.yaml`).
2. Open [Render Blueprint](https://dashboard.render.com/select-repo?type=blueprint) and select the repo.
3. Fill sync:false env vars:

| Variable | Example |
|----------|---------|
| `BACKEND_PUBLIC_URL` | `https://mailmind-backend.onrender.com` |
| `FRONTEND_URL` | `https://your-app.vercel.app` |
| `CORS_ORIGINS` | `https://your-app.vercel.app` |
| `TOKEN_ENCRYPTION_KEY` | Fernet key from `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | From Google Cloud Console |
| `GROQ_API_KEY` | Groq key |

4. After deploy, copy the backend URL into Vercel `VITE_API_BASE_URL` and redeploy the frontend.

## 2b. Use Supabase for Postgres

Supabase is a good fit for the database layer only. Keep the FastAPI backend, Redis,
Google OAuth, and Gmail sync jobs exactly as they are.

1. Create a Supabase project.
2. In Supabase, open the Postgres connection details and copy the **direct** connection string.
3. Set backend `DATABASE_URL` to that value, using the async SQLAlchemy form:

```txt
postgresql+asyncpg://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres?ssl=require
```

4. Keep `REDIS_URL` pointed at Redis (Render/Upstash/local).
5. Run migrations against Supabase:

```powershell
cd mailmind-ai-backend
alembic upgrade head
```

Notes:

- Prefer the direct database host for migrations and app traffic.
- If Supabase gives you a `postgresql://...` URL, this backend will normalize it to
  `postgresql+asyncpg://...` automatically.
- Do **not** switch this app to Supabase Auth unless you intend to refactor the current
  backend-managed Google login/session flow.

## 3. Google OAuth Console

Authorized JavaScript origins:

- `https://your-app.vercel.app`

Authorized redirect URIs:

- `https://YOUR-API-HOST/api/v1/auth/google/callback`

## Local vs production cookies

Production uses `SameSite=None; Secure` refresh cookies so the Vercel origin can call the API with `credentials: "include"`.
