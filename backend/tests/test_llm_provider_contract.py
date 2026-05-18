from __future__ import annotations

import dataclasses
import json
import time

import anyio
import httpx
import pytest

from aqbox.config import LLMModerationPolicy
from aqbox.llm_provider import (
    DeepSeekLLMProvider,
    LLMProviderErrorClass,
    build_llm_provider_request,
)
from aqbox.moderation import build_llm_moderation_prompt


def make_policy(
    *,
    base_url: str = "https://api.deepseek.test",
    api_key_value: str = "test-secret",
    timeout_seconds: float = 3.0,
    max_tokens: int = 192,
) -> LLMModerationPolicy:
    return LLMModerationPolicy(
        owner="owner",
        question_type="confession",
        policy_prompt="Escalate repeat fan-drama bait for this owner console.",
        provider="deepseek",
        base_url=base_url,
        model="deepseek-v4-flash",
        api_key_env="AQBOX_TEST_LLM_KEY",
        api_key_value=api_key_value,
        high_confidence_reject_threshold=0.85,
        review_all_model_rejects=True,
        max_attempts=2,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        initial_backoff_seconds=0.5,
    )


def deepseek_success_response(
    *,
    content: str = (
        '{"decision":"accept","moderation_category":"safe","confidence":0.99,"short_reason":"Safe submission","rationale":"No concern."}'
    ),
    finish_reason: str = "stop",
    model: str = "deepseek-v4-flash",
) -> dict[str, object]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 31, "completion_tokens": 17, "total_tokens": 48},
    }


def run_call_with_transport(
    handler: httpx.MockTransport,
    *,
    policy: LLMModerationPolicy | None = None,
    request_updates: dict[str, object] | None = None,
):
    async def _call():
        selected_policy = policy or make_policy()
        async with httpx.AsyncClient(transport=handler) as client:
            provider = DeepSeekLLMProvider(http_client=client)
            prompt = build_llm_moderation_prompt(selected_policy, "A gentle safe submission.")
            request = build_llm_provider_request(prompt=prompt, policy=selected_policy)
            if request_updates:
                request = dataclasses.replace(request, **request_updates)
            return await provider.complete(request)

    return anyio.run(_call)


def test_deepseek_provider_request_disables_raw_capture_by_default() -> None:
    policy = make_policy()
    prompt = build_llm_moderation_prompt(policy, "A gentle safe submission.")
    request = build_llm_provider_request(prompt=prompt, policy=policy)

    assert request.capture_raw_response is False


def test_deepseek_provider_can_opt_into_raw_capture() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=deepseek_success_response())

    result = run_call_with_transport(httpx.MockTransport(handler), request_updates={"capture_raw_response": True})

    assert result.error_class is None
    assert result.raw_response is not None
    assert result.raw_response["id"] == "chatcmpl-test"


def test_deepseek_provider_sanitizes_success_response_by_default() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=deepseek_success_response())

    result = run_call_with_transport(httpx.MockTransport(handler))

    assert result.error_class is None
    assert result.raw_response is None


def test_deepseek_provider_sanitizes_invalid_success_envelope_by_default() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "deepseek-v4-flash", "choices": []})

    result = run_call_with_transport(httpx.MockTransport(handler))

    assert result.error_class == "invalid_response"
    assert result.raw_response is None


def test_deepseek_provider_can_opt_into_raw_invalid_success_envelope_capture() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "deepseek-v4-flash", "choices": []})

    result = run_call_with_transport(httpx.MockTransport(handler), request_updates={"capture_raw_response": True})

    assert result.error_class == "invalid_response"
    assert result.raw_response == {"model": "deepseek-v4-flash", "choices": []}


def test_deepseek_provider_applies_end_to_end_deadline_to_slow_provider_response() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await anyio.sleep(0.05)
        return httpx.Response(200, json=deepseek_success_response())

    started = time.perf_counter()
    result = run_call_with_transport(
        httpx.MockTransport(handler),
        policy=make_policy(timeout_seconds=0.01),
    )
    elapsed = time.perf_counter() - started

    assert result.error_class == "timeout"
    assert result.http_status is None
    assert calls == 1
    assert elapsed < 0.04


def test_deepseek_provider_posts_provider_generic_chat_request_without_retries() -> None:
    captured: dict[str, object] = {}
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["timeout"] = request.extensions.get("timeout")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=deepseek_success_response())

    result = run_call_with_transport(httpx.MockTransport(handler))

    body = captured["body"]
    assert captured["url"] == "https://api.deepseek.test/chat/completions"
    assert captured["authorization"] == "Bearer test-secret"
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-v4-flash"
    assert body["messages"]
    assert body["stream"] is False
    assert body["temperature"] == pytest.approx(0.1)
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 192
    assert "max_retries" not in body
    assert calls == 1
    assert captured["timeout"] == {"connect": 3.0, "read": 3.0, "write": 3.0, "pool": 3.0}
    assert result.error_class is None
    assert result.content is not None
    assert result.finish_reason == "stop"
    assert result.model == "deepseek-v4-flash"
    assert result.usage.prompt_tokens == 31
    assert result.usage.completion_tokens == 17
    assert result.usage.total_tokens == 48
    assert result.latency_ms >= 0


@pytest.mark.parametrize(
    "finish_reason",
    [
        "stop",
        "length",
        "content_filter",
    ],
)
def test_deepseek_provider_preserves_finish_reason_for_parser_boundary(finish_reason: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=deepseek_success_response(content="", finish_reason=finish_reason))

    result = run_call_with_transport(httpx.MockTransport(handler))

    assert result.error_class is None
    assert result.content == ""
    assert result.finish_reason == finish_reason


@pytest.mark.parametrize(
    ("status_code", "expected_error_class"),
    [
        (400, "config_auth"),
        (401, "config_auth"),
        (403, "config_auth"),
        (404, "config_auth"),
        (402, "quota_exceeded"),
        (429, "rate_limited"),
        (500, "server"),
        (503, "server"),
    ],
)
def test_deepseek_provider_classifies_http_errors(status_code: int, expected_error_class: LLMProviderErrorClass) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": {"message": "provider rejected request", "type": "test"}})

    result = run_call_with_transport(httpx.MockTransport(handler))

    assert result.error_class == expected_error_class
    assert result.http_status == status_code
    assert result.content is None
    assert result.finish_reason is None


def test_deepseek_provider_classifies_timeout() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout")

    result = run_call_with_transport(httpx.MockTransport(handler))

    assert result.error_class == "timeout"
    assert result.http_status is None


def test_deepseek_provider_classifies_network_errors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    result = run_call_with_transport(httpx.MockTransport(handler))

    assert result.error_class == "network"
    assert result.http_status is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"{not-json"),
        httpx.Response(200, json={"model": "deepseek-v4-flash", "choices": []}),
        httpx.Response(200, json={"model": "deepseek-v4-flash", "choices": [{"message": {}, "finish_reason": "stop"}]}),
        httpx.Response(200, json={"model": "deepseek-v4-flash", "choices": [{"message": {"content": "ok"}}]}),
    ],
)
def test_deepseek_provider_classifies_invalid_provider_envelopes(response: httpx.Response) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    result = run_call_with_transport(httpx.MockTransport(handler))

    assert result.error_class == "invalid_response"
    assert result.content is None
    assert result.finish_reason is None


def test_deepseek_provider_classifies_missing_api_key_as_config_auth_without_network() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("missing API key should not perform a network request")

    result = run_call_with_transport(httpx.MockTransport(handler), policy=make_policy(api_key_value=""))

    assert result.error_class == "config_auth"
    assert result.http_status is None
