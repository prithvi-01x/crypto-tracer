from fastapi import APIRouter
from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.auth import router as auth_router
from backend.app.api.v1.endpoints.cases import router as cases_router
from backend.app.api.v1.endpoints.blockchain import router as blockchain_router

api_v1_router = APIRouter()

# Phase 0 endpoints
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)

# Phase 1 endpoints
api_v1_router.include_router(cases_router)

# Phase 2 endpoints
api_v1_router.include_router(blockchain_router)
