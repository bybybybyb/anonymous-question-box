from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic, time
from typing import Any

from .config import Settings, load_settings

RESTART_REQUIRED_FIELDS = {
    "host",
    "port",
    "db_path",
    "jwt_secret_key",
    "magic_spell",
    "llm_filter",
}


@dataclass(slots=True)
class ConfigStatus:
    version: int
    loaded_at: float
    hash: str
    last_reload_error: str | None
    restart_required: list[str]


class SettingsProvider:
    def __init__(
        self,
        *,
        config_path: str | None = None,
        settings: Settings | None = None,
        check_interval_seconds: float = 0.25,
    ):
        self.config_path = config_path or (settings.config_path if settings else None)
        self._settings = settings or load_settings(config_path)
        self._static = settings is not None and config_path is None
        self._check_interval_seconds = check_interval_seconds
        self._next_check_at = 0.0
        self._signature = self._read_signature()
        self._hash = self._signature[2]
        self._version = 1
        self._loaded_at = time()
        self._last_reload_error: str | None = None
        self._restart_required: set[str] = set()

    def current(self, *, force: bool = False) -> Settings:
        if not self._static:
            self._maybe_reload(force=force)
        return self._settings

    def status(self) -> ConfigStatus:
        self.current()
        return ConfigStatus(
            version=self._version,
            loaded_at=self._loaded_at,
            hash=self._hash,
            last_reload_error=self._last_reload_error,
            restart_required=sorted(self._restart_required),
        )

    def status_dict(self) -> dict[str, Any]:
        status = self.status()
        return {
            "version": status.version,
            "loaded_at": status.loaded_at,
            "hash": status.hash,
            "last_reload_error": status.last_reload_error,
            "restart_required": status.restart_required,
        }

    @property
    def healthy(self) -> bool:
        return self.status().last_reload_error is None

    def _maybe_reload(self, *, force: bool) -> None:
        now = monotonic()
        if not force and now < self._next_check_at:
            return
        self._next_check_at = now + self._check_interval_seconds
        signature = self._read_signature()
        if not force and signature == self._signature:
            return
        try:
            loaded = load_settings(self.config_path)
            merged, restart_required = self._merge_restart_required(self._settings, loaded)
        except Exception as exc:
            self._last_reload_error = str(exc)
            return
        self._settings = merged
        self._signature = signature
        self._hash = signature[2]
        self._version += 1
        self._loaded_at = time()
        self._last_reload_error = None
        self._restart_required = restart_required

    def _read_signature(self) -> tuple[int, int, str]:
        if not self.config_path:
            return (0, 0, "")
        path = Path(self.config_path)
        try:
            stat = path.stat()
            data = path.read_bytes()
        except OSError:
            return (0, 0, "")
        return (stat.st_mtime_ns, stat.st_size, hashlib.sha256(data).hexdigest())

    @staticmethod
    def _merge_restart_required(active: Settings, loaded: Settings) -> tuple[Settings, set[str]]:
        restart_required: set[str] = set()
        replacements: dict[str, Any] = {}
        for field in RESTART_REQUIRED_FIELDS:
            if getattr(active, field) != getattr(loaded, field):
                restart_required.add(field)
                replacements[field] = getattr(active, field)
        if replacements:
            loaded = replace(loaded, **replacements)
        return loaded, restart_required
