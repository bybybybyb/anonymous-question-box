from __future__ import annotations

import math
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

IP2REGION_CACHE_POLICIES = {"file", "vectorIndex", "content"}


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


def _as_bool(value: Any, *, default: bool = False, field_name: str = "boolean") -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise ValueError(f"{field_name} must be a boolean")


def _as_float(value: Any, *, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _as_probability(value: Any, *, default: float, field_name: str) -> float:
    probability = _as_float(value, default=default)
    if not math.isfinite(probability) or probability < 0.0 or probability > 1.0:
        raise ValueError(f"{field_name} must be a finite number between 0 and 1")
    return probability


def _as_int(value: Any, *, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True, slots=True)
class LLMQuestionTypeConfig:
    enabled: bool = False
    policy_prompt: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class LLMBoxConfig:
    question_types: dict[str, LLMQuestionTypeConfig] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class LLMModerationPolicy:
    owner: str
    question_type: str
    policy_prompt: str
    provider: str
    base_url: str
    model: str
    api_key_env: str
    api_key_value: str = field(repr=False)
    high_confidence_reject_threshold: float
    review_all_model_rejects: bool
    max_attempts: int
    timeout_seconds: float
    max_tokens: int
    initial_backoff_seconds: float

    def api_key(self) -> str:
        env_key = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        if env_key:
            return env_key
        return self.api_key_value


@dataclass(frozen=True, slots=True)
class LLMModerationConfig:
    enabled: bool = False
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    api_key_env: str = "DEEPSEEK_API_KEY"
    api_key_value: str = field(default="", repr=False)
    high_confidence_reject_threshold: float = 0.85
    review_all_model_rejects: bool = True
    max_attempts: int = 2
    timeout_seconds: float = 10.0
    max_tokens: int = 256
    initial_backoff_seconds: float = 1.0
    raw_retention_enabled: bool = False
    raw_retention_seconds: int = 0
    boxes: dict[str, LLMBoxConfig] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def api_key(self) -> str:
        env_key = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        if env_key:
            return env_key
        return self.api_key_value

    def policy_for(self, owner: str, qtype: str) -> LLMModerationPolicy | None:
        if not self.enabled:
            return None
        qtype_config = self.boxes.get(owner, LLMBoxConfig()).question_types.get(qtype)
        if qtype_config is None or not qtype_config.enabled:
            return None
        return LLMModerationPolicy(
            owner=owner,
            question_type=qtype,
            policy_prompt=qtype_config.policy_prompt,
            provider=self.provider,
            base_url=self.base_url,
            model=self.model,
            api_key_env=self.api_key_env,
            api_key_value=self.api_key_value,
            high_confidence_reject_threshold=self.high_confidence_reject_threshold,
            review_all_model_rejects=self.review_all_model_rejects,
            max_attempts=self.max_attempts,
            timeout_seconds=self.timeout_seconds,
            max_tokens=self.max_tokens,
            initial_backoff_seconds=self.initial_backoff_seconds,
        )

    def public_status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key_env": self.api_key_env,
            "api_key_configured": bool(self.api_key()),
            "high_confidence_reject_threshold": self.high_confidence_reject_threshold,
            "review_all_model_rejects": self.review_all_model_rejects,
            "max_attempts": self.max_attempts,
            "timeout_seconds": self.timeout_seconds,
            "max_tokens": self.max_tokens,
            "initial_backoff_seconds": self.initial_backoff_seconds,
            "raw_retention_enabled": self.raw_retention_enabled,
            "raw_retention_seconds": self.raw_retention_seconds,
            "boxes": {
                owner: {
                    "question_types": {
                        qtype: {
                            "enabled": qtype_config.enabled,
                            "policy_prompt_configured": qtype_config.policy_prompt != "",
                        }
                        for qtype, qtype_config in box.question_types.items()
                    }
                }
                for owner, box in self.boxes.items()
            },
        }


def _parse_llm_moderation_config(raw: dict[str, Any]) -> LLMModerationConfig:
    provider = str(raw.get("provider") or "deepseek")
    api_key_env = str(raw.get("api_key_env") or ("DEEPSEEK_API_KEY" if provider == "deepseek" else ""))
    raw_retention_seconds = raw.get("raw_retention_seconds")
    if raw_retention_seconds is None and raw.get("raw_retention_days") is not None:
        raw_retention_seconds = _as_int(raw.get("raw_retention_days"), default=0) * 86400
    boxes: dict[str, LLMBoxConfig] = {}
    boxes_raw = _as_map_by_name(raw.get("boxes") or raw.get("owners"))
    for owner, box_raw in boxes_raw.items():
        question_types: dict[str, LLMQuestionTypeConfig] = {}
        for qtype, qtype_raw in _as_map_by_name(box_raw.get("question_types")).items():
            policy_prompt = qtype_raw.get("policy_prompt", qtype_raw.get("prompt", ""))
            question_types[qtype] = LLMQuestionTypeConfig(
                enabled=_as_bool(
                    qtype_raw.get("enabled"),
                    default=False,
                    field_name=f"llm_filter boxes.{owner}.question_types.{qtype}.enabled",
                ),
                policy_prompt="" if policy_prompt is None else str(policy_prompt),
                raw=dict(qtype_raw),
            )
        boxes[owner] = LLMBoxConfig(question_types=question_types, raw=dict(box_raw))
    return LLMModerationConfig(
        enabled=_as_bool(raw.get("enabled"), default=False, field_name="llm_filter.enabled"),
        provider=provider,
        base_url=str(raw.get("base_url") or raw.get("api_base_url") or "https://api.deepseek.com"),
        model=str(raw.get("model") or "deepseek-v4-flash"),
        api_key_env=api_key_env,
        api_key_value=str(raw.get("api_key") or ""),
        high_confidence_reject_threshold=_as_probability(
            raw.get("high_confidence_reject_threshold", raw.get("confidence_threshold")),
            default=0.85,
            field_name="llm_filter.high_confidence_reject_threshold",
        ),
        review_all_model_rejects=_as_bool(
            raw.get("review_all_model_rejects"), default=True, field_name="llm_filter.review_all_model_rejects"
        ),
        max_attempts=max(1, _as_int(raw.get("max_attempts"), default=2)),
        timeout_seconds=max(0.1, _as_float(raw.get("timeout_seconds"), default=10.0)),
        max_tokens=max(1, _as_int(raw.get("max_tokens"), default=256)),
        initial_backoff_seconds=max(0.0, _as_float(raw.get("initial_backoff_seconds"), default=1.0)),
        raw_retention_enabled=_as_bool(raw.get("raw_retention_enabled"), default=False, field_name="llm_filter.raw_retention_enabled"),
        raw_retention_seconds=max(0, _as_int(raw_retention_seconds, default=0)),
        boxes=boxes,
        raw=dict(raw),
    )


@dataclass(slots=True)
class Settings:
    """Runtime configuration after normalizing legacy YAML shapes into dicts keyed by name."""

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
    geo_enabled: bool = True
    trusted_proxy_cidrs: list[str] = field(default_factory=lambda: ["127.0.0.1/32", "::1/128"])
    ip2region_ipv4_xdb_path: str = ""
    ip2region_ipv6_xdb_path: str = ""
    ip2region_cache_policy: str = "vectorIndex"
    llm_filter: dict[str, Any] = field(default_factory=dict, repr=False)
    llm_moderation: LLMModerationConfig = field(default_factory=LLMModerationConfig)

    def __post_init__(self) -> None:
        self.llm_filter = dict(self.llm_filter or {})
        if self.llm_filter:
            self.llm_moderation = _parse_llm_moderation_config(self.llm_filter)

    def public_profiles(self) -> dict[str, Any]:
        """Return public profile config with image upload forcibly disabled for Python v2."""
        profiles = deepcopy(self.owner_profiles)
        for owner in profiles.values():
            for qtype in owner.get("question_types", {}).values():
                qtype["support_image"] = False
        return {"owner_profiles": profiles, "metadata": deepcopy(self.metadata)}

    def question_type(self, owner: str, qtype: str) -> dict[str, Any] | None:
        question_types = self.owner_profiles.get(owner, {}).get("question_types", {})
        if not isinstance(question_types, dict):
            return None
        return cast("dict[str, Any] | None", question_types.get(qtype))

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
    ip2region_cache_policy = str(raw.get("ip2region_cache_policy", "vectorIndex"))
    if ip2region_cache_policy not in IP2REGION_CACHE_POLICIES:
        raise ValueError(f"unsupported ip2region_cache_policy {ip2region_cache_policy}")
    llm_filter = dict(raw.get("llm_filter") or {})
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
        geo_enabled=bool(raw.get("geo_enabled", True)),
        trusted_proxy_cidrs=list(raw.get("trusted_proxy_cidrs") or ["127.0.0.1/32", "::1/128"]),
        ip2region_ipv4_xdb_path=str(raw.get("ip2region_ipv4_xdb_path", "")),
        ip2region_ipv6_xdb_path=str(raw.get("ip2region_ipv6_xdb_path", "")),
        ip2region_cache_policy=ip2region_cache_policy,
        llm_filter=llm_filter,
    )
