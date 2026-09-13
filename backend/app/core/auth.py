"""
Crypto-Tracer: Core Authentication & RBAC Engine.
Supports RS256 (OIDC/RSA) and HS256 JWT signature verification,
claims extraction, and role normalization.
"""
from enum import Enum
from typing import Optional, Union, List, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import jwt
from pydantic import BaseModel, Field

from backend.app.config import (
    settings,
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)


class Role(str, Enum):
    """Canonical 4-Role Role-Based Access Control (RBAC) definitions."""
    INVESTIGATING_OFFICER = "INVESTIGATING_OFFICER"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"
    AUDITOR = "AUDITOR"


ROLE_NORMALIZATION_MAP: Dict[str, Role] = {
    "ROLE_INVESTIGATOR": Role.INVESTIGATING_OFFICER,
    "ROLE_INVESTIGATING_OFFICER": Role.INVESTIGATING_OFFICER,
    "INVESTIGATOR": Role.INVESTIGATING_OFFICER,
    "INVESTIGATING_OFFICER": Role.INVESTIGATING_OFFICER,
    "IO": Role.INVESTIGATING_OFFICER,
    "ROLE_SUPERVISOR": Role.SUPERVISOR,
    "SUPERVISOR": Role.SUPERVISOR,
    "ROLE_ADMIN": Role.ADMIN,
    "ADMIN": Role.ADMIN,
    "ADMINISTRATOR": Role.ADMIN,
    "ROLE_AUDITOR": Role.AUDITOR,
    "AUDITOR": Role.AUDITOR,
}


def normalize_role(raw_role: Any) -> str:
    """Normalizes role strings from diverse identity providers into canonical Role values."""
    if isinstance(raw_role, Role):
        return raw_role.value
    if not raw_role:
        return Role.INVESTIGATING_OFFICER.value
    key = str(raw_role).strip().upper()
    return ROLE_NORMALIZATION_MAP.get(key, Role.INVESTIGATING_OFFICER).value


class TokenClaims(BaseModel):
    """Decoded and validated JWT claims payload."""
    sub: str = Field(..., description="Subject identifier / Officer Unique ID")
    badge_number: Optional[str] = Field(None, description="Officer badge / service number")
    role: str = Field(Role.INVESTIGATING_OFFICER.value, description="Assigned role")
    tenant_id: str = Field(DEFAULT_TENANT_ID, description="Tenant / State agency ID")
    district_id: str = Field(DEFAULT_DISTRICT_ID, description="District jurisdiction ID")
    police_station_id: str = Field(DEFAULT_POLICE_STATION_ID, description="Police station ID")
    iss: Optional[str] = None
    aud: Optional[Union[str, List[str]]] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    nbf: Optional[int] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    email: Optional[str] = None


class OfficerSession(BaseModel):
    """Authenticated investigator session and jurisdictional tenant context."""
    officer_id: str
    name: str
    badge_number: str
    unit: str
    role: str
    is_authenticated: bool = True
    tenant_id: str = DEFAULT_TENANT_ID
    district_id: str = DEFAULT_DISTRICT_ID
    police_station_id: str = DEFAULT_POLICE_STATION_ID
    station_id: str = DEFAULT_POLICE_STATION_ID


class AuthError(Exception):
    """Exception raised for authentication errors with structured error payload."""
    def __init__(self, message: str, code: str = "UNAUTHORIZED", status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class JWTAuthEngine:
    """JWT Verification and Claims extraction engine supporting RS256 and HS256."""

    def __init__(self):
        self._test_rsa_private_key: Optional[bytes] = None
        self._test_rsa_public_key: Optional[bytes] = None

    def get_public_key(self) -> Union[str, bytes]:
        """Resolves the RSA public key from settings or cached test key."""
        if settings.JWT_PUBLIC_KEY and settings.JWT_PUBLIC_KEY.strip():
            return settings.JWT_PUBLIC_KEY.strip()
        if settings.JWT_PUBLIC_KEY_PATH and os.path.exists(settings.JWT_PUBLIC_KEY_PATH):
            with open(settings.JWT_PUBLIC_KEY_PATH, "rb") as f:
                return f.read()
        if self._test_rsa_public_key:
            return self._test_rsa_public_key
        raise AuthError("No RS256 public key configured.", code="UNAUTHORIZED")

    def decode_token(self, token: str, algorithms: Optional[List[str]] = None) -> TokenClaims:
        """
        Decodes and validates a raw JWT token, verifying signature and standard claims.
        """
        if not token or not token.strip():
            raise AuthError("Token is empty.", code="UNAUTHORIZED")

        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise AuthError(f"Invalid token header: {str(e)}", code="UNAUTHORIZED")

        alg = unverified_header.get("alg", settings.JWT_ALGORITHM)
        allowed_algs = algorithms or [alg, "RS256", "HS256"]

        # Determine verification key
        if alg == "RS256":
            key = self.get_public_key()
        elif alg == "HS256":
            key = settings.jwt_secret_key_value
        else:
            raise AuthError(f"Unsupported JWT algorithm: {alg}", code="UNAUTHORIZED")

        verify_options: Dict[str, Any] = {
            "verify_signature": True,
            "verify_exp": True,
        }

        # Optional audience and issuer validation
        aud = settings.JWT_AUDIENCE or settings.OIDC_AUDIENCE
        iss = settings.OIDC_ISSUER

        decode_kwargs: Dict[str, Any] = {
            "algorithms": allowed_algs,
            "options": verify_options,
        }
        if aud:
            decode_kwargs["audience"] = aud
        else:
            decode_kwargs["options"]["verify_aud"] = False

        if iss:
            decode_kwargs["issuer"] = iss
        else:
            decode_kwargs["options"]["verify_iss"] = False

        try:
            payload = jwt.decode(token, key, **decode_kwargs)
        except jwt.ExpiredSignatureError:
            raise AuthError("Token has expired.", code="UNAUTHORIZED")
        except jwt.InvalidSignatureError:
            raise AuthError("Invalid token signature.", code="UNAUTHORIZED")
        except jwt.InvalidAudienceError:
            raise AuthError("Invalid token audience.", code="UNAUTHORIZED")
        except jwt.InvalidIssuerError:
            raise AuthError("Invalid token issuer.", code="UNAUTHORIZED")
        except (jwt.DecodeError, jwt.InvalidTokenError) as e:
            raise AuthError(f"Invalid authentication token: {str(e)}", code="UNAUTHORIZED")

        # Extract claims with fallbacks
        sub = payload.get("sub") or payload.get("officer_id") or "OFFICER-UNKNOWN"
        role_raw = payload.get("role") or payload.get("roles")
        if isinstance(role_raw, list):
            role_raw = role_raw[0] if role_raw else "INVESTIGATING_OFFICER"
        norm_role = normalize_role(role_raw)

        tenant_id = payload.get("tenant_id") or DEFAULT_TENANT_ID
        district_id = payload.get("district_id") or DEFAULT_DISTRICT_ID
        # Handle station_id alias
        police_station_id = (
            payload.get("police_station_id")
            or payload.get("station_id")
            or DEFAULT_POLICE_STATION_ID
        )

        return TokenClaims(
            sub=str(sub),
            badge_number=payload.get("badge_number"),
            role=norm_role,
            tenant_id=str(tenant_id),
            district_id=str(district_id),
            police_station_id=str(police_station_id),
            iss=payload.get("iss"),
            aud=payload.get("aud"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            nbf=payload.get("nbf"),
            name=payload.get("name"),
            unit=payload.get("unit"),
            email=payload.get("email"),
        )


jwt_auth_engine = JWTAuthEngine()


def create_access_token(
    claims: Dict[str, Any],
    algorithm: str = "HS256",
    key: Optional[Union[str, bytes]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Utility to create signed JWT tokens for tests and development."""
    to_encode = claims.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=1)
    to_encode.setdefault("exp", int(expire.timestamp()))
    to_encode.setdefault("iat", int(now.timestamp()))

    signing_key = key or (settings.jwt_secret_key_value if algorithm == "HS256" else None)
    if not signing_key:
        raise ValueError("A valid signing key is required to encode token.")

    return jwt.encode(to_encode, signing_key, algorithm=algorithm)


def decode_access_token(token: str) -> TokenClaims:
    """Convenience helper to decode and validate JWT access token."""
    return jwt_auth_engine.decode_token(token)

