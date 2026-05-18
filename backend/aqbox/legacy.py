from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .schemas import model_from_payload


class LegacyAPIError(Exception):
    """Error shape used by Go-era routes: HTTP status plus `{"error": ...}` body."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


def legacy_error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


async def read_body(request: Request, action: str) -> dict[str, Any]:
    """Read JSON manually so legacy routes never expose FastAPI's default 422 envelope."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise LegacyAPIError(400, f"无法读取{action}请求，错误信息：{exc}") from exc
    return payload if isinstance(payload, dict) else {}


def parse_model(model: type, payload: dict[str, Any], action: str) -> Any:
    """Convert payloads through Pydantic while preserving legacy Chinese error envelopes."""
    try:
        return model_from_payload(model, payload)
    except ValidationError as exc:
        raise LegacyAPIError(400, f"无法解析{action}请求，错误信息：{exc}") from exc
