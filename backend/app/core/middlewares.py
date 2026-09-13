"""
Crypto-Tracer Security Middlewares & Telemetry Context.

Provides:
- CorrelationIdMiddleware: Inbound/outbound X-Correlation-ID tracking with async ContextVar.
- SecurityHeadersMiddleware: OWASP defense-in-depth HTTP security headers.
- apply_security_headers: Standalone utility for injecting headers into any response or error envelope.
"""
import uuid
from typing import MutableMapping, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from backend.app.config import settings
from backend.app.logging import correlation_id_ctx, get_correlation_id

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none';",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

HSTS_HEADER_NAME = "Strict-Transport-Security"
HSTS_HEADER_VALUE = "max-age=31536000; includeSubDomains"


def is_secure_transport(request: Optional[Request] = None, enforce_hsts: bool = False) -> bool:
    """Determine whether request was transported over HTTPS or HSTS is globally enforced."""
    if enforce_hsts or getattr(settings, "SECURE_HSTS_ENABLED", None) is True or getattr(settings, "APP_ENV", "").lower() == "production":
        return True
    if request is not None:
        if request.url.scheme == "https":
            return True
        if request.headers.get("x-forwarded-proto", "").lower() == "https":
            return True
    return False


def apply_security_headers(
    headers: MutableMapping[str, str],
    request: Optional[Request] = None,
    enforce_hsts: bool = False,
) -> None:
    """
    Inject security headers into any mutable headers dictionary.
    Used by middlewares and global exception handlers to guarantee uniform security headers.
    """
    for header_name, header_val in SECURITY_HEADERS.items():
        headers[header_name] = header_val

    if is_secure_transport(request=request, enforce_hsts=enforce_hsts):
        headers[HSTS_HEADER_NAME] = HSTS_HEADER_VALUE


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware for end-to-end request correlation tracking and telemetry.
    Reads incoming X-Correlation-ID or generates a standard UUID4.
    Attaches to request.state.correlation_id, updates async ContextVar,
    and sets outbound X-Correlation-ID response header.
    """
    def __init__(self, app: ASGIApp, header_name: str = "X-Correlation-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound_id = request.headers.get(self.header_name)
        if inbound_id and inbound_id.strip() and len(inbound_id.strip()) <= 128:
            corr_id = inbound_id.strip()
        else:
            corr_id = str(uuid.uuid4())

        request.state.correlation_id = corr_id
        token = correlation_id_ctx.set(corr_id)
        try:
            response = await call_next(request)
            response.headers[self.header_name] = corr_id
            return response
        finally:
            correlation_id_ctx.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware injecting OWASP security headers into all HTTP responses.
    """
    def __init__(self, app: ASGIApp, enforce_hsts: Optional[bool] = None):
        super().__init__(app)
        self.enforce_hsts = (
            enforce_hsts
            if enforce_hsts is not None
            else (getattr(settings, "APP_ENV", "").lower() == "production")
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        apply_security_headers(
            response.headers,
            request=request,
            enforce_hsts=self.enforce_hsts,
        )
        return response
