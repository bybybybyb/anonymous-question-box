from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request

LOGGER = logging.getLogger("aqbox.request")


async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        safe_path = request.url.path
        if request.url.query:
            safe_path = f"{safe_path}?<redacted>"
        LOGGER.info(
            "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            safe_path,
            status_code,
            duration_ms,
            request_id,
        )
