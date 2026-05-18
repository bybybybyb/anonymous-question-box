from __future__ import annotations

import dataclasses
import json

import pytest

from aqbox.config import LLMModerationPolicy
from aqbox.moderation import (
    LLM_MODERATION_PROMPT_VERSION,
    LLM_MODERATION_RATIONALE_MAX_LENGTH,
    LLM_MODERATION_SHORT_REASON_MAX_LENGTH,
    InvalidLLMModerationResponseError,
    build_llm_moderation_prompt,
    parse_llm_moderation_response,
)


def make_policy(*, policy_prompt: str = "Escalate repeat fan-drama bait for this owner console.") -> LLMModerationPolicy:
    return LLMModerationPolicy(
        owner="owner",
        question_type="confession",
        policy_prompt=policy_prompt,
        provider="deepseek",
        base_url="https://api.deepseek.test",
        model="deepseek-v4-flash",
        api_key_env="AQBOX_TEST_LLM_KEY",
        api_key_value="do-not-leak-secret",
        high_confidence_reject_threshold=0.85,
        review_all_model_rejects=True,
        max_attempts=2,
        timeout_seconds=3.0,
        max_tokens=192,
        initial_backoff_seconds=0.5,
    )


@pytest.mark.parametrize(
    "submission_text",
    [
        "I liked your latest answer and hope your day is going well.",
        "Someone should post this person's home address in the chat.",
        "Are you secretly the person from that private account?",
        "You are worthless and everyone here should mock you.",
        "I will hurt the asker if this gets ignored.",
        "This fandom fight proves your fans are all fake traitors.",
        "Cheap followers, crypto tips, and promo links here.",
    ],
)
def test_llm_prompt_includes_domain_contract_terms_and_safe_fixture_layers(submission_text: str) -> None:
    prompt = build_llm_moderation_prompt(make_policy(), submission_text)
    prompt_payload = dataclasses.asdict(prompt)
    prompt_text = "\n".join(message["content"] for message in prompt.messages)

    assert prompt.prompt_version == LLM_MODERATION_PROMPT_VERSION
    assert prompt.response_format == {"type": "json_object"}
    assert prompt.max_tokens == 192
    assert prompt.policy_hash
    assert prompt.messages[-1]["role"] == "user"
    assert "<<<QUESTION>>>" in prompt.messages[-1]["content"]
    assert "<<<END_QUESTION>>>" in prompt.messages[-1]["content"]
    assert submission_text in prompt.messages[-1]["content"]
    for term in [
        "submission",
        "asker",
        "owner console",
        "question type",
        "review queue",
        "moderation category",
    ]:
        assert term in prompt_text
    for policy_term in [
        "privacy",
        "doxxing",
        "identity speculation",
        "harassment",
        "threats",
        "spam",
        "explicit sexual content",
        "fan drama",
        "other",
    ]:
        assert policy_term in prompt_text
    assert "json" in prompt_text.lower()
    assert (
        json.dumps(
            {
                "decision": "reject",
                "moderation_category": "harassment",
                "confidence": 0.92,
                "short_reason": "Harassing or abusive submission",
                "rationale": "The submission targets a person with abusive language.",
            }
        )
        in prompt_text
    )
    assert "Escalate repeat fan-drama bait" in prompt_text
    assert "do-not-leak-secret" not in json.dumps(prompt_payload)
    assert "AQBOX_TEST_LLM_KEY" not in prompt_text
    assert "https://api.deepseek.test" not in prompt_text
    for forbidden in [
        "client IP",
        "IP location",
        "owner/admin token",
        "matched keyword",
        "full keyword list",
        "asker JWT",
        "submission UUID",
    ]:
        assert forbidden not in prompt_text


def test_llm_prompt_allows_empty_additive_owner_policy() -> None:
    prompt = build_llm_moderation_prompt(make_policy(policy_prompt=""), "A gentle safe submission.")

    prompt_text = "\n".join(message["content"] for message in prompt.messages)
    assert "Additional owner/question-type policy:" in prompt_text
    assert "No additional owner/question-type policy." in prompt_text


def test_parse_llm_moderation_response_accepts_strict_stop_json_object() -> None:
    parsed = parse_llm_moderation_response(
        finish_reason="stop",
        content=json.dumps(
            {
                "decision": "reject",
                "moderation_category": "doxxing",
                "confidence": 0.91,
                "short_reason": "Doxxing or private identifying details",
                "rationale": "The submission asks the owner to expose private identifying details.",
            }
        ),
        original_text="please expose their home address",
    )

    assert parsed.decision == "reject"
    assert parsed.moderation_category == "doxxing"
    assert parsed.confidence == pytest.approx(0.91)
    assert parsed.short_reason == "Doxxing or private identifying details"
    assert parsed.rationale.startswith("The submission asks")


@pytest.mark.parametrize(
    ("finish_reason", "expected_code"),
    [
        ("length", "non_stop_finish_reason"),
        ("content_filter", "non_stop_finish_reason"),
        ("insufficient_system_resource", "non_stop_finish_reason"),
    ],
)
def test_parse_llm_moderation_response_rejects_non_stop_finish_reasons(finish_reason: str, expected_code: str) -> None:
    with pytest.raises(InvalidLLMModerationResponseError) as exc:
        parse_llm_moderation_response(
            finish_reason=finish_reason,
            content=json.dumps(
                {
                    "decision": "accept",
                    "moderation_category": "safe",
                    "confidence": 0.99,
                    "short_reason": "Safe submission",
                    "rationale": "No moderation concern was found.",
                }
            ),
        )

    assert exc.value.code == expected_code


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        ("", "empty_content"),
        ('```json\n{"decision":"accept"}\n```', "invalid_json"),
        ('Result: {"decision":"accept"}', "invalid_json"),
        ("[]", "non_json_object"),
        ("{}", "missing_field"),
        (
            json.dumps(
                {
                    "decision": "accept",
                    "moderation_category": "safe",
                    "confidence": 0.7,
                    "short_reason": "Safe submission",
                    "rationale": "No issue.",
                    "extra": "not allowed",
                }
            ),
            "extra_field",
        ),
        (
            json.dumps(
                {
                    "decision": "maybe",
                    "moderation_category": "safe",
                    "confidence": 0.7,
                    "short_reason": "Safe submission",
                    "rationale": "No issue.",
                }
            ),
            "invalid_decision",
        ),
        (
            json.dumps(
                {
                    "decision": [],
                    "moderation_category": "safe",
                    "confidence": 0.7,
                    "short_reason": "Safe submission",
                    "rationale": "No issue.",
                }
            ),
            "schema_mismatch",
        ),
        (
            json.dumps(
                {
                    "decision": "reject",
                    "moderation_category": "not_site_tuned",
                    "confidence": 0.7,
                    "short_reason": "Unknown category",
                    "rationale": "No issue.",
                }
            ),
            "unknown_moderation_category",
        ),
        (
            '{"decision":"reject","moderation_category":"spam","confidence":NaN,"short_reason":"Spam","rationale":"Promotional content."}',
            "invalid_json",
        ),
        (
            json.dumps(
                {
                    "decision": "reject",
                    "moderation_category": "spam",
                    "confidence": 1.01,
                    "short_reason": "Spam",
                    "rationale": "Promotional content.",
                }
            ),
            "invalid_confidence",
        ),
        (
            json.dumps(
                {
                    "decision": "reject",
                    "moderation_category": "spam",
                    "confidence": 0.8,
                    "short_reason": "x" * (LLM_MODERATION_SHORT_REASON_MAX_LENGTH + 1),
                    "rationale": "Promotional content.",
                }
            ),
            "string_too_long",
        ),
        (
            json.dumps(
                {
                    "decision": "reject",
                    "moderation_category": "spam",
                    "confidence": 0.8,
                    "short_reason": "Spam",
                    "rationale": "x" * (LLM_MODERATION_RATIONALE_MAX_LENGTH + 1),
                }
            ),
            "string_too_long",
        ),
    ],
)
def test_parse_llm_moderation_response_rejects_invalid_output(content: str, expected_code: str) -> None:
    with pytest.raises(InvalidLLMModerationResponseError) as exc:
        parse_llm_moderation_response(finish_reason="stop", content=content)

    assert exc.value.code == expected_code


def test_parse_llm_moderation_response_rejects_short_reason_that_quotes_original_submission() -> None:
    original_text = "please leak the private phone number"
    with pytest.raises(InvalidLLMModerationResponseError) as exc:
        parse_llm_moderation_response(
            finish_reason="stop",
            content=json.dumps(
                {
                    "decision": "reject",
                    "moderation_category": "doxxing",
                    "confidence": 0.93,
                    "short_reason": f"Quotes original: {original_text}",
                    "rationale": "The submission asks for private contact details.",
                }
            ),
            original_text=original_text,
        )

    assert exc.value.code == "unsafe_short_reason"
