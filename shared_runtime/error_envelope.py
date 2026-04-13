"""error_envelope — shared HTTP error response normalisation.

Registers FastAPI exception handlers that add ``error`` (machine-readable type)
and ``correlation_id`` fields alongside the standard FastAPI ``detail`` field.

Existing tests that assert ``body["detail"]`` continue to pass because the
``detail`` value is preserved exactly as FastAPI produces it.  The new fields
are purely additive.

Usage (in each service's application factory)::

    from shared_runtime.error_envelope import install_error_handlers
    install_error_handlers(app)

Resulting envelope for all 4xx / 5xx responses::

    {
        "error": "not_found",          # machine-readable type
        "detail": "mission not found", # FastAPI-standard value (unchanged)
        "correlation_id": "abc123"     # from request.state.correlation_id
    }
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Map HTTP status codes to short machine-readable error type strings.
_ERROR_TYPE: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    408: "request_timeout",
    409: "conflict",
    410: "gone",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}


def _error_type(status_code: int) -> str:
    return _ERROR_TYPE.get(status_code, f"http_{status_code}")


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "") or ""


def install_error_handlers(app: FastAPI) -> None:
    """Register normalising exception handlers on *app*.

    Must be called after the app is created and before it starts handling
    requests.  Calling it twice is safe (handlers are replaced, not stacked).
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": _error_type(exc.status_code),
                "detail": exc.detail,
                "correlation_id": _correlation_id(request),
            },
            headers=getattr(exc, "headers", None) or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": exc.errors(),
                "correlation_id": _correlation_id(request),
            },
        )
