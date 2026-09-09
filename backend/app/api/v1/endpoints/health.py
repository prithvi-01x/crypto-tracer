from datetime import datetime, timezone
from fastapi import APIRouter
from backend.app.config import settings
from backend.app.persistence.db import check_db_connection
from backend.app.persistence.redis import check_redis_connection
from backend.app.api.v1.schemas.health import HealthResponse, ServiceComponentHealth

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health():
    db_health = await check_db_connection()
    redis_health = await check_redis_connection()

    overall_healthy = (
        db_health.get("status") == "HEALTHY" and
        redis_health.get("status") == "HEALTHY"
    )

    return HealthResponse(
        status="HEALTHY" if overall_healthy else "DEGRADED",
        app=settings.APP_NAME,
        environment=settings.APP_ENV,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc),
        services={
            "database": ServiceComponentHealth(**db_health),
            "redis": ServiceComponentHealth(**redis_health),
        }
    )
