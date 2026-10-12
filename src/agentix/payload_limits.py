"""Bound mutation bodies before parsing JSON or opening a database transaction."""

from starlette.responses import JSONResponse

MAX_REQUEST_BYTES = 100_000
SIZE_ERROR = "Request body exceeds 100,000 bytes. Shorten the content and try again."


class PayloadLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "PUT", "DELETE"}:
            return await self.app(scope, receive, send)

        async def reject():
            request_id = scope.get("state", {}).get("request_id")
            response = JSONResponse(
                {
                    "detail": SIZE_ERROR,
                    "error": {"status": 413, "request_id": request_id, "retryable": False},
                },
                status_code=413,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)

        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    if int(value) > MAX_REQUEST_BYTES:
                        return await reject()
                except ValueError:
                    pass  # Still enforce the actual streamed byte count.
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_REQUEST_BYTES:
                return await reject()
            if chunk:
                chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
