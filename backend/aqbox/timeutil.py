from __future__ import annotations

from datetime import UTC, datetime


def now_epoch() -> int:
    return int(datetime.now(tz=UTC).timestamp())


def rfc3339_from_epoch(value: int | None) -> str:
    if not value:
        value = 0
    return datetime.fromtimestamp(int(value), tz=UTC).isoformat().replace("+00:00", "Z")
