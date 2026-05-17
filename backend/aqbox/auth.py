from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any

import jwt

from .config import Settings

TOKEN_EXPIRATION_DAYS = 100000


@dataclass(slots=True)
class Principal:
    uuid: str
    is_admin: bool


def generate_token(settings: Settings, uuid: str) -> str:
    now = int(time())
    claims = {
        "uuid": uuid,
        "exp": now + TOKEN_EXPIRATION_DAYS * 24 * 60 * 60,
        "iat": now,
    }
    encoded = jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")
    return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded


def validate_token(settings: Settings, encoded_token: str) -> Principal:
    claims: dict[str, Any] = jwt.decode(encoded_token, settings.jwt_secret_key, algorithms=["HS256"])
    if settings.magic_spell in claims:
        return Principal(uuid=str(claims[settings.magic_spell]), is_admin=True)
    if "uuid" in claims:
        return Principal(uuid=str(claims["uuid"]), is_admin=False)
    raise ValueError("validation failed or decoding failed")


def bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.split("Bearer ")
    if len(parts) == 2:
        return parts[1]
    return None
