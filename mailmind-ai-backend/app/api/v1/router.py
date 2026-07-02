from fastapi import APIRouter

from app.api.v1 import ai, auth, cleanup, dashboard, emails, health, inbox, search, settings

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_v1_router.include_router(emails.router, prefix="/emails", tags=["emails"])
api_v1_router.include_router(inbox.router, prefix="/inbox", tags=["inbox"])
api_v1_router.include_router(cleanup.router, prefix="/cleanup", tags=["cleanup"])
api_v1_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_v1_router.include_router(search.router, prefix="/search", tags=["search"])
api_v1_router.include_router(settings.router, prefix="/settings", tags=["settings"])
