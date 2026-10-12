"""Request correlation and stable error metadata for automated clients."""

import uuid

from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from agentix.payload_limits import PayloadLimitMiddleware


def mount_operations(app):
    app.add_middleware(PayloadLimitMiddleware)

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith(("/v1/", "/health/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def error_response(request, exc, handler):
        import json

        response = await handler(request, exc)
        body = json.loads(response.body)
        body["error"] = {
            "status": response.status_code,
            "request_id": request.state.request_id,
            "retryable": response.status_code in (429, 502, 503, 504),
        }
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store"
        return JSONResponse(body, status_code=response.status_code, headers=headers)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return await error_response(request, exc, http_exception_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return await error_response(request, exc, request_validation_exception_handler)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        # ServerErrorMiddleware sits outside user middleware: set headers here too.
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            {
                "detail": "Internal error",
                "error": {"status": 500, "request_id": request_id, "retryable": False},
            },
            status_code=500,
            headers={
                "Cache-Control": "no-store",
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
            },
        )
