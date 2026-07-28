#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
python - <<'PY'
import asyncio
import os
import sys
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

database_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://mailmind:mailmind@postgres:5432/mailmind",
)
if database_url.startswith("postgres://"):
    database_url = "postgresql+asyncpg://" + database_url[len("postgres://") :]
elif database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
    database_url = "postgresql+asyncpg://" + database_url[len("postgresql://") :]

async def wait_for_db() -> None:
    deadline = time.time() + 60
    last_error: Exception | None = None
    while time.time() < deadline:
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("PostgreSQL is ready.")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            await asyncio.sleep(2)
        finally:
            await engine.dispose()
    raise SystemExit(f"PostgreSQL not ready: {last_error}")

asyncio.run(wait_for_db())
PY

echo "Running database migrations..."
alembic upgrade head

echo "Starting MailMind API..."
PORT="${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
