from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx

from .config import LLMModerationPolicy
from .moderation import LLMModerationPrompt

LLMProviderErrorClass = Literal[
    "config_auth",
    "rate_limited",
    "timeout",
    "network",
    "server",
    "invalid_response",
    "quota_exceeded",
]


@dataclass(frozen=True, slots=True)
class LLMProviderRequest:
    messages: list[dict[str, str]]
    model: str
    timeout_seconds: float
    response_format: dict[str, str] | None
    max_tokens: int
    base_url: str
    api_key: str = field(repr=False)
    capture_raw_response: bool = False


@dataclass(frozen=True, slots=True)
class LLMProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMProviderResponse:
    content: str | None
    finish_reason: str | None
    model: str | None
    latency_ms: float
    usage: LLMProviderUsage = field(default_factory=LLMProviderUsage)
    error_class: LLMProviderErrorClass | None = None
    http_status: int | None = None
    provider_error_message: str | None = field(default=None, repr=False)
    raw_response: dict[str, Any] | None = field(default=None, repr=False)


class LLMProvider(Protocol):
    async def complete(self, request: LLMProviderRequest) -> LLMProviderResponse: ...


def build_llm_provider_request(*, prompt: LLMModerationPrompt, policy: LLMModerationPolicy) -> LLMProviderRequest:
    return LLMProviderRequest(
        messages=prompt.messages,
        model=policy.model,
        timeout_seconds=policy.timeout_seconds,
        response_format=prompt.response_format,
        max_tokens=prompt.max_tokens,
        base_url=policy.base_url,
        api_key=policy.api_key(),
    )


class DeepSeekLLMProvider:
    def __init__(self, *, http_client: httpx.AsyncClient | None = None):
        self._client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None

    async def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        started = time.perf_counter()
        if not request.api_key:
            return self._error_response(started, "config_auth")
        try:
            response = await asyncio.wait_for(
                self._client.post(
                    _chat_completions_url(request.base_url),
                    headers={"Authorization": f"Bearer {request.api_key}"},
                    json=_deepseek_payload(request),
                    timeout=request.timeout_seconds,
                ),
                timeout=request.timeout_seconds,
            )
        except (TimeoutError, httpx.TimeoutException):
            return self._error_response(started, "timeout")
        except httpx.RequestError:
            return self._error_response(started, "network")

        if response.status_code >= 400:
            return self._error_response(
                started,
                _classify_http_status(response.status_code),
                http_status=response.status_code,
                provider_error_message=_provider_error_message(response),
            )
        try:
            envelope = response.json()
        except ValueError:
            return self._error_response(started, "invalid_response", http_status=response.status_code)
        if not isinstance(envelope, dict):
            return self._error_response(started, "invalid_response", http_status=response.status_code)
        return _parse_success_envelope(
            envelope,
            started,
            response.status_code,
            capture_raw_response=request.capture_raw_response,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _error_response(
        self,
        started: float,
        error_class: LLMProviderErrorClass,
        *,
        http_status: int | None = None,
        provider_error_message: str | None = None,
    ) -> LLMProviderResponse:
        return LLMProviderResponse(
            content=None,
            finish_reason=None,
            model=None,
            latency_ms=_elapsed_ms(started),
            error_class=error_class,
            http_status=http_status,
            provider_error_message=provider_error_message,
        )


def _deepseek_payload(request: LLMProviderRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": request.messages,
        "temperature": 0.1,
        "stream": False,
        "max_tokens": request.max_tokens,
    }
    if request.response_format is not None:
        payload["response_format"] = request.response_format
    return payload


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _classify_http_status(status_code: int) -> LLMProviderErrorClass:
    if status_code == 402:
        return "quota_exceeded"
    if status_code in {400, 401, 403, 404}:
        return "config_auth"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code <= 599:
        return "server"
    return "invalid_response"


def _provider_error_message(response: httpx.Response) -> str | None:
    try:
        envelope = response.json()
    except ValueError:
        return None
    if not isinstance(envelope, Mapping):
        return None
    error = envelope.get("error")
    if not isinstance(error, Mapping):
        return None
    message = error.get("message")
    return message if isinstance(message, str) else None


def _parse_success_envelope(
    envelope: dict[str, Any],
    started: float,
    http_status: int,
    *,
    capture_raw_response: bool,
) -> LLMProviderResponse:
    model = envelope.get("model")
    choices = envelope.get("choices")
    if not isinstance(model, str) or not isinstance(choices, list) or not choices:
        return _invalid_response(started, http_status, envelope, capture_raw_response=capture_raw_response)
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        return _invalid_response(started, http_status, envelope, capture_raw_response=capture_raw_response)
    finish_reason = first_choice.get("finish_reason")
    message = first_choice.get("message")
    if not isinstance(finish_reason, str) or not isinstance(message, Mapping):
        return _invalid_response(started, http_status, envelope, capture_raw_response=capture_raw_response)
    content = message.get("content")
    if not isinstance(content, str):
        return _invalid_response(started, http_status, envelope, capture_raw_response=capture_raw_response)
    return LLMProviderResponse(
        content=content,
        finish_reason=finish_reason,
        model=model,
        latency_ms=_elapsed_ms(started),
        usage=_parse_usage(envelope.get("usage")),
        http_status=http_status,
        raw_response=envelope if capture_raw_response else None,
    )


def _parse_usage(value: Any) -> LLMProviderUsage:
    if not isinstance(value, Mapping):
        return LLMProviderUsage()
    return LLMProviderUsage(
        prompt_tokens=_optional_int(value.get("prompt_tokens")),
        completion_tokens=_optional_int(value.get("completion_tokens")),
        total_tokens=_optional_int(value.get("total_tokens")),
    )


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _invalid_response(
    started: float,
    http_status: int,
    envelope: dict[str, Any],
    *,
    capture_raw_response: bool,
) -> LLMProviderResponse:
    return LLMProviderResponse(
        content=None,
        finish_reason=None,
        model=None,
        latency_ms=_elapsed_ms(started),
        error_class="invalid_response",
        http_status=http_status,
        raw_response=envelope if capture_raw_response else None,
    )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0
