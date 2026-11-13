"""Bound ingress before JSON parsing, including bodies without Content-Length."""
from fastapi.responses import JSONResponse


class IngressBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PATCH"):
            return await self.app(scope, receive, send)
        path = scope["path"].rstrip("/")
        limit = 4096 if path in ("/api/telemetry", "/api/exercises/telemetry") else 8192 if path.startswith("/api/stations") else None
        if path.startswith(("/api/auth/","/api/users", "/api/sos", "/api/response-resources")):limit=16384
        if path.startswith(('/api/notification-receipts','/api/notification-deliveries')):limit=4096
        if path.startswith(('/api/forecast-registry','/api/forecast-deployments')):limit=4096
        if limit is None:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None:
            try:
                excessive = int(length) < 0 or int(length) > limit
            except ValueError:
                excessive = True
            if excessive:
                return await JSONResponse({"detail": "Request body exceeds the ingress budget."}, 413)(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                return await JSONResponse({"detail": "Request body exceeds the ingress budget."}, 413)(scope, receive, send)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
