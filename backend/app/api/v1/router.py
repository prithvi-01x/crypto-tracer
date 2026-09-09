from fastapi import APIRouter
from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.auth import router as auth_router

api_v1_router = APIRouter()

# Phase 0 endpoints
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
