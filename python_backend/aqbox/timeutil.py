from __future__ import annotations

from datetime import datetime, timezone


def now_epoch() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def rfc3339_from_epoch(value: int | None) -> str:
    if not value:
        value = 0
    return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")

