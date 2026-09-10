from fastapi import APIRouter
from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.auth import router as auth_router
from backend.app.api.v1.endpoints.cases import router as cases_router
from backend.app.api.v1.endpoints.traces import router as traces_router
from backend.app.api.v1.endpoints.evidence import router as evidence_router
from backend.app.api.v1.endpoints.reports import router as reports_router
from backend.app.api.v1.endpoints.demo import router as demo_router

api_v1_router = APIRouter()

# Phase 0 endpoints
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)

# Phase 1 endpoints
api_v1_router.include_router(cases_router)

# Phase 3-6 endpoints
api_v1_router.include_router(traces_router)

# Phase 7 endpoints
api_v1_router.include_router(evidence_router)

# Phase 8 endpoints
api_v1_router.include_router(reports_router)

# Phase 10 Demo Replay & Reset endpoints
api_v1_router.include_router(demo_router)
