"""
FastAPI Request Dependencies for Crypto-Tracer:
- get_current_officer: Extracts Bearer JWT token, validates signatures (RS256/HS256),
  and returns authenticated OfficerSession. Provides environment-aware mock fallback in dev/test.
- require_roles: Role-Based Access Control (RBAC) dependency verifying officer permissions.
"""
from typing import List, Optional, Union
from fastapi import Depends, Header, HTTPException, Request, status

from backend.app.config import (
    settings,
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)
from backend.app.core.auth import (
    Role,
    TokenClaims,
    OfficerSession,
    jwt_auth_engine,
    normalize_role,
    AuthError,
)


async def get_current_officer(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> OfficerSession:
    """
    Extracts and verifies the Bearer JWT token from the Authorization header.
    
    Environment-aware fallback:
    - If Authorization header is missing and APP_ENV != "production", returns a default
      investigating officer session for backward compatibility with existing tests.
    - If APP_ENV == "production", missing or invalid Authorization header strictly raises
      HTTP 401 Unauthorized with standardized error payload.
    - If Authorization header is provided, it is always validated regardless of APP_ENV.
    """
    is_production = settings.APP_ENV.lower() == "production"

    if not authorization or not authorization.strip():
        if is_production:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "UNAUTHORIZED",
                    "message": "Missing Authorization header with Bearer token.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Development / Test backward-compatibility fallback
        return OfficerSession(
            officer_id="OFFICER-DL-812",
            name="Inspector P. Sharma",
            badge_number="CYBER-DELHI-4029",
            unit="District Cyber Crime Cell, IFSO Unit",
            role=Role.INVESTIGATING_OFFICER.value,
            is_authenticated=True,
            tenant_id=DEFAULT_TENANT_ID,
            district_id=DEFAULT_DISTRICT_ID,
            police_station_id=DEFAULT_POLICE_STATION_ID,
            station_id=DEFAULT_POLICE_STATION_ID,
        )

    # Token provided: validate schema format
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Invalid Authorization header format. Expected 'Bearer <token>'.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = parts[1]

    try:
        claims: TokenClaims = jwt_auth_engine.decode_token(raw_token)
    except AuthError as err:
        raise HTTPException(
            status_code=err.status_code,
            detail={
                "code": err.code,
                "message": err.message,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": f"Token verification failed: {str(err)}",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return OfficerSession(
        officer_id=claims.sub,
        name=claims.name or f"Officer {claims.sub}",
        badge_number=claims.badge_number or "UNASSIGNED",
        unit=claims.unit or "Cyber Crime Investigation Unit",
        role=claims.role,
        is_authenticated=True,
        tenant_id=claims.tenant_id,
        district_id=claims.district_id,
        police_station_id=claims.police_station_id,
        station_id=claims.police_station_id,
    )


def require_roles(allowed_roles: List[Union[Role, str]]):
    """
    Dependency factory that enforces Role-Based Access Control (RBAC).
    Normalizes input roles and checks if the requesting officer's role is authorized.
    Raises HTTP 403 Forbidden with standardized error code if unauthorized.
    """
    normalized_allowed = set()
    for r in allowed_roles:
        if isinstance(r, Role):
            normalized_allowed.add(r.value)
        else:
            normalized_allowed.add(normalize_role(str(r)))

    async def role_checker(
        current_officer: OfficerSession = Depends(get_current_officer),
    ) -> OfficerSession:
        user_role = normalize_role(current_officer.role)
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": (
                        f"Role '{current_officer.role}' is not authorized to access this resource. "
                        f"Allowed roles: {sorted(list(normalized_allowed))}."
                    ),
                },
            )
        return current_officer

    return role_checker
