from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.config import settings
from backend.app.logging import setup_logging, logger
from backend.app.core.middlewares import (
    CorrelationIdMiddleware,
    SecurityHeadersMiddleware,
)
from backend.app.core.errors import register_exception_handlers
from backend.app.api.v1.router import api_v1_router
from backend.app.persistence.db import engine, check_db_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings.validate_production_invariants()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")

    # Verify database connectivity on startup without mutating schema (DDL managed solely via Alembic)
    try:
        health = await check_db_connection()
        if health["status"] == "HEALTHY":
            logger.info(f"Database connection verified (latency: {health['latency_ms']}ms).")
        else:
            logger.warning(f"Database connection check returned unhealthy status: {health.get('error')}")
    except Exception as e:
        logger.warning(f"Database connection check deferred/unreachable on startup: {e}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated Attribution of Unknown Cryptocurrency Wallets to Nearest VASPs",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Register centralized exception handlers (dual envelope with correlation ID)
register_exception_handlers(app)

# Middlewares are added in reverse execution order for requests:
# Inbound: CorrelationIdMiddleware -> SecurityHeadersMiddleware -> TrustedHostMiddleware -> CORSMiddleware
# Outbound: CORSMiddleware -> TrustedHostMiddleware -> SecurityHeadersMiddleware -> CorrelationIdMiddleware

# 1. CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

# 2. Trusted Host middleware
if settings.ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# 3. Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# 4. Correlation ID middleware (outermost)
app.add_middleware(CorrelationIdMiddleware)

# Mount API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# Mount WebSocket router
from backend.app.api.v1.endpoints.ws import router as ws_router
app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ONLINE",
        "docs": f"{settings.API_V1_STR}/docs",
        "api_v1": settings.API_V1_STR,
    }
