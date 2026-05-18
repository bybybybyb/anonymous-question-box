from __future__ import annotations

import logging
from time import perf_counter
from urllib.parse import parse_qsl, quote_plus
from uuid import uuid4

from fastapi import Request

LOGGER = logging.getLogger("aqbox.request")
SECRET_QUERY_KEYS = {"token"}


def _safe_path(request: Request) -> str:
    """Redact secret query values without hiding useful operational parameters."""
    if not request.url.query:
        return request.url.path
    parts = []
    for key, value in parse_qsl(request.url.query, keep_blank_values=True):
        safe_value = "<redacted>" if key.lower() in SECRET_QUERY_KEYS else quote_plus(value)
        if key.lower() in SECRET_QUERY_KEYS:
            parts.append(f"{quote_plus(key)}={safe_value}")
            continue
        parts.append(f"{quote_plus(key)}={safe_value}")
    return f"{request.url.path}?{'&'.join(parts)}"


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
        LOGGER.info(
            "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            _safe_path(request),
            status_code,
            duration_ms,
            request_id,
        )
