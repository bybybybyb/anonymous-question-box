from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _as_map_by_name(value: Any) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): _normalize_named(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        result: dict[str, dict[str, Any]] = {}
        for item in value:
            if isinstance(item, dict) and item.get("name"):
                result[str(item["name"])] = _normalize_named(item, str(item["name"]))
        return result
    return {}


def _normalize_named(value: Any, fallback_name: str) -> dict[str, Any]:
    item = dict(value or {})
    item.setdefault("name", fallback_name)
    return item


def _normalize_owner_profiles(raw_profiles: Any) -> dict[str, dict[str, Any]]:
    profiles = _as_map_by_name(raw_profiles)
    for owner_name, owner in profiles.items():
        owner.setdefault("name", owner_name)
        owner.setdefault("colors", {})
        owner["colors"].setdefault("primary_color", "")
        owner["colors"].setdefault("secondary_color", "")
        qtypes = _as_map_by_name(owner.get("question_types"))
        for qtype_name, qtype in qtypes.items():
            qtype.setdefault("name", qtype_name)
            qtype.setdefault("description", "")
            qtype.setdefault("rune_limit", 0)
            qtype.setdefault("theme", {})
            qtype["theme"].setdefault("name", "")
            qtype["theme"].setdefault("background_class", "")
            qtype.setdefault("support_image", False)
        owner["question_types"] = qtypes
    return profiles


@dataclass(slots=True)
class Settings:
    config_path: str = "./config/config.yaml"
    host: str = ""
    port: int = 8080
    db_path: str = "aqbox.sqlite3"
    db_max_connections: int = 1
    jwt_secret_key: str = ""
    magic_spell: str = "magic_spell"
    default_rune_limit: int = 500
    filtered_keywords: list[str] = field(default_factory=list)
    owner_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=lambda: {"introductions": [], "console_prints": [], "admin": {}})
    visit_flush_interval_seconds: float = 10.0
    geo_enabled: bool = False
    trusted_proxy_cidrs: list[str] = field(default_factory=lambda: ["127.0.0.1/32", "::1/128"])
    pconline_geo_url: str = "https://whois.pconline.com.cn/ipJson.jsp"
    geo_timeout_seconds: float = 3.0
    llm_filter: dict[str, Any] = field(default_factory=dict)

    def public_profiles(self) -> dict[str, Any]:
        profiles = deepcopy(self.owner_profiles)
        for owner in profiles.values():
            for qtype in owner.get("question_types", {}).values():
                qtype["support_image"] = False
        return {"owner_profiles": profiles, "metadata": deepcopy(self.metadata)}

    def question_type(self, owner: str, qtype: str) -> dict[str, Any] | None:
        return self.owner_profiles.get(owner, {}).get("question_types", {}).get(qtype)

    def rune_limit(self, owner: str, qtype: str) -> tuple[int, bool]:
        question_type = self.question_type(owner, qtype)
        if question_type is None:
            return self.default_rune_limit, False
        return int(question_type.get("rune_limit") or self.default_rune_limit), True


def load_settings(config_path: str | None = None) -> Settings:
    path = Path(config_path or "./config/config.yaml")
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

    metadata = raw.get("website_metadata") or raw.get("metadata") or {}
    metadata = {
        "introductions": list(metadata.get("introductions") or []),
        "console_prints": list(metadata.get("console_prints") or []),
        "admin": dict(metadata.get("admin") or {}),
    }
    return Settings(
        config_path=str(path),
        host=str(raw.get("host", "")),
        port=int(raw.get("port", 8080)),
        db_path=str(raw.get("db_path", "aqbox.sqlite3")),
        db_max_connections=int(raw.get("db_max_connections", 1) or 1),
        jwt_secret_key=str(raw.get("jwt_secret_key", "")),
        magic_spell=str(raw.get("magic_spell", "magic_spell")),
        default_rune_limit=int(raw.get("default_rune_limit", 500)),
        filtered_keywords=[str(keyword) for keyword in (raw.get("filtered_keywords") or [])],
        owner_profiles=_normalize_owner_profiles(raw.get("owner_profiles")),
        metadata=metadata,
        visit_flush_interval_seconds=float(raw.get("visit_flush_interval_seconds", 10.0)),
        geo_enabled=bool(raw.get("geo_enabled", False)),
        trusted_proxy_cidrs=list(raw.get("trusted_proxy_cidrs") or ["127.0.0.1/32", "::1/128"]),
        pconline_geo_url=str(raw.get("pconline_geo_url", "https://whois.pconline.com.cn/ipJson.jsp")),
        geo_timeout_seconds=float(raw.get("geo_timeout_seconds", 3.0)),
        llm_filter=dict(raw.get("llm_filter") or {}),
    )
