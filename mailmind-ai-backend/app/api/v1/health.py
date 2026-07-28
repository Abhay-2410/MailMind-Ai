from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.redis import get_redis
from app.db.session import check_database_connection
from app.middleware.rate_limit import apply_rate_limit

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
@apply_rate_limit("30/minute")
async def liveness_check(request: Request) -> HealthResponse:
    _ = request
    return HealthResponse(
        status="ok",
        service="mailmind-ai-backend",
        timestamp=datetime.now(UTC),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
@apply_rate_limit("30/minute")
async def readiness_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ReadinessResponse | JSONResponse:
    _ = request
    _ = db
    db_ok = await check_database_connection()

    redis_ok = False
    try:
        redis_ok = bool(await redis.ping())
    except Exception:
        redis_ok = False

    all_ok = db_ok and redis_ok
    payload = ReadinessResponse(
        status="ok" if all_ok else "degraded",
        database="ok" if db_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
        timestamp=datetime.now(UTC),
    )
    if not all_ok:
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))
    return payload
