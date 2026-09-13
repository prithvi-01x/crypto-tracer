"""
Centralized Exception Handlers and Standardized Dual Error Envelopes.

Formats all error responses into a dual envelope:
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable description",
        "timestamp": "ISO-8601 UTC timestamp",
        "trace_id": "X-Correlation-ID"
    },
    "detail": ... (legacy compatible structure)
}
"""
import traceback
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Union
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.config import settings
from backend.app.core.middlewares import apply_security_headers
from backend.app.logging import logger, get_correlation_id

STATUS_CODE_TO_ERROR_CODE: Dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def get_request_trace_id(request: Request) -> str:
    """Extract correlation ID from request state, active logging context, or headers."""
    if hasattr(request, "state") and getattr(request.state, "correlation_id", None):
        return str(request.state.correlation_id)
    cid = get_correlation_id()
    if cid and cid != "-":
        return cid
    header_id = request.headers.get("X-Correlation-ID")
    if header_id and header_id.strip():
        return header_id.strip()
    return str(uuid.uuid4())


def get_utc_timestamp() -> str:
    """Return ISO-8601 formatted UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Standardized exception handler for Starlette and FastAPI HTTPExceptions.
    Formats response with dual envelope (top-level 'error' + backward-compatible 'detail').
    """
    trace_id = get_request_trace_id(request)
    timestamp = get_utc_timestamp()
    status_code = exc.status_code

    if isinstance(exc.detail, dict):
        error_code = exc.detail.get("code") or STATUS_CODE_TO_ERROR_CODE.get(status_code, "HTTP_ERROR")
        error_message = exc.detail.get("message") or str(exc.detail)
        detail_payload: Union[Dict[str, Any], str] = exc.detail
    else:
        error_code = STATUS_CODE_TO_ERROR_CODE.get(status_code, "HTTP_ERROR")
        error_message = str(exc.detail) if exc.detail is not None else "An error occurred."
        detail_payload = exc.detail if exc.detail is not None else error_message

    response_payload = {
        "error": {
            "code": error_code,
            "message": error_message,
            "timestamp": timestamp,
            "trace_id": trace_id,
        },
        "detail": detail_payload,
    }

    headers: Dict[str, str] = {"X-Correlation-ID": trace_id}
    apply_security_headers(headers, request=request)

    return JSONResponse(
        status_code=status_code,
        content=response_payload,
        headers=headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Standardized exception handler for Pydantic RequestValidationErrors.
    Returns HTTP 422 with validation error details and dual envelope.
    """
    trace_id = get_request_trace_id(request)
    timestamp = get_utc_timestamp()
    errors = jsonable_encoder(exc.errors())

    response_payload = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "timestamp": timestamp,
            "trace_id": trace_id,
            "details": errors,
        },
        "detail": errors,
    }

    headers: Dict[str, str] = {"X-Correlation-ID": trace_id}
    apply_security_headers(headers, request=request)

    status_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    return JSONResponse(
        status_code=status_422,
        content=response_payload,
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler for uncaught server errors (HTTP 500).
    In production: Masks internal tracebacks and returns generic error message.
    In development/test: Returns exception name and traceback for debugging.
    """
    trace_id = get_request_trace_id(request)
    timestamp = get_utc_timestamp()
    is_production = settings.APP_ENV.lower() == "production"

    logger.error(
        f"Unhandled exception caught on {request.method} {request.url.path} [trace_id={trace_id}]: {exc}",
        exc_info=True,
    )

    if is_production:
        error_message = "Internal server error"
        error_body = {
            "code": "INTERNAL_SERVER_ERROR",
            "message": error_message,
            "timestamp": timestamp,
            "trace_id": trace_id,
        }
        detail_body = {
            "code": "INTERNAL_SERVER_ERROR",
            "message": error_message,
        }
    else:
        error_message = f"{type(exc).__name__}: {str(exc)}"
        tb_str = traceback.format_exc()
        error_body = {
            "code": "INTERNAL_SERVER_ERROR",
            "message": error_message,
            "timestamp": timestamp,
            "trace_id": trace_id,
            "traceback": tb_str,
        }
        detail_body = {
            "code": "INTERNAL_SERVER_ERROR",
            "message": error_message,
            "traceback": tb_str,
        }

    response_payload = {
        "error": error_body,
        "detail": detail_body,
    }

    headers: Dict[str, str] = {"X-Correlation-ID": trace_id}
    apply_security_headers(headers, request=request)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_payload,
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized error envelope handlers on the FastAPI application."""
    from fastapi.exceptions import HTTPException as FastAPIHTTPException

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
