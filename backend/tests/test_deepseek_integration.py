from __future__ import annotations

import os

import anyio
import pytest

from aqbox.config import LLMModerationConfig, LLMModerationPolicy
from aqbox.llm_provider import DeepSeekLLMProvider, build_llm_provider_request
from aqbox.moderation import build_llm_moderation_prompt, parse_llm_moderation_response

# Mirror the shipped defaults so this opt-in test exercises what production sends.
_DEFAULTS = LLMModerationConfig()


def make_policy() -> LLMModerationPolicy:
    return LLMModerationPolicy(
        owner="integration-owner",
        question_type="confession",
        policy_prompt="Reject doxxing, private identifying details, harassment, threats, spam, and unsafe fan drama.",
        provider="deepseek",
        base_url=os.environ.get("DEEPSEEK_BASE_URL", _DEFAULTS.base_url),
        model=os.environ.get("DEEPSEEK_MODEL", _DEFAULTS.model),
        api_key_env="DEEPSEEK_API_KEY",
        api_key_value="",
        high_confidence_reject_threshold=0.85,
        review_all_model_rejects=True,
        max_attempts=1,
        timeout_seconds=float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", _DEFAULTS.timeout_seconds)),
        # deepseek-flash runs in thinking mode and this provider never disables it, so
        # chain-of-thought is counted in completion_tokens and consumes the max_tokens
        # budget before the final JSON content is emitted. A cap that is too small
        # truncates the reply to finish_reason="length", which
        # parse_llm_moderation_response rejects as finish_reason_length instead of
        # returning a decision. Wall-clock time needs headroom for the same reason.
        max_tokens=int(os.environ.get("DEEPSEEK_MAX_TOKENS", _DEFAULTS.max_tokens)),
        initial_backoff_seconds=0.0,
    )


@pytest.mark.parametrize(
    ("submission_text", "expected_decision"),
    [
        ("I hope your day is peaceful and I liked your answer.", "accept"),
        ("Please post the askers private home address and phone number.", "reject"),
    ],
)
def test_real_deepseek_json_moderation_contract_opt_in(submission_text: str, expected_decision: str) -> None:
    if os.environ.get("AQBOX_RUN_DEEPSEEK_INTEGRATION") != "1":
        pytest.skip("Set AQBOX_RUN_DEEPSEEK_INTEGRATION=1 and DEEPSEEK_API_KEY to call DeepSeek; this may incur cost or rate limits.")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("Set DEEPSEEK_API_KEY with AQBOX_RUN_DEEPSEEK_INTEGRATION=1 to call DeepSeek; this may incur cost or rate limits.")

    async def _call_real_deepseek():
        policy = make_policy()
        provider = DeepSeekLLMProvider()
        prompt = build_llm_moderation_prompt(policy, submission_text)
        try:
            result = await provider.complete(build_llm_provider_request(prompt=prompt, policy=policy))
        finally:
            await provider.aclose()
        assert result.error_class is None
        assert result.model
        assert result.finish_reason
        assert result.latency_ms >= 0
        parsed = parse_llm_moderation_response(
            finish_reason=result.finish_reason,
            content=result.content,
            original_text=submission_text,
        )
        assert parsed.decision == expected_decision
        assert submission_text.lower() not in parsed.short_reason.lower()

    anyio.run(_call_real_deepseek)
