"""Privacy-conscious HTTP request logging for the local Clinic Front-Desk API.

Records only a generated request ID, HTTP method, matched route template,
status and elapsed time. Deliberately never logs raw URLs, query strings,
request bodies, cookies, headers or patient identifiers.
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request


logger = logging.getLogger("clinic.request")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def install_request_logging(app: FastAPI) -> None:
    """Register privacy-conscious logging on the supplied FastAPI app."""

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        status = 500

        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Log route templates, never request.url.path or query strings.
            # /auth/callback?code=SECRET is recorded only as /auth/callback.
            route = request.scope.get("route")
            safe_route = getattr(route, "path", "unmatched")

            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": safe_route,
                "status": status,
                "duration_ms": round(
                    (time.perf_counter() - start) * 1000, 2
                ),
            }
            logger.info(json.dumps(event, separators=(",", ":")))
