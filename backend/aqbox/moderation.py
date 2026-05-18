from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal, cast

from .config import LLMModerationPolicy

LLM_MODERATION_PROMPT_VERSION = "aqbox-moderation-v1"
LLM_MODERATION_SHORT_REASON_MAX_LENGTH = 120
LLM_MODERATION_RATIONALE_MAX_LENGTH = 800

LLM_MODERATION_CATEGORIES = frozenset(
    {
        "safe",
        "privacy",
        "doxxing",
        "identity_speculation",
        "harassment",
        "threats",
        "spam",
        "explicit_sexual_content",
        "fan_drama",
        "other",
    }
)
_LLM_RESPONSE_FIELDS = frozenset({"decision", "moderation_category", "confidence", "short_reason", "rationale"})


@dataclass(slots=True)
class FilterResult:
    blocked: bool
    source: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class LLMModerationPrompt:
    messages: list[dict[str, str]]
    prompt_version: str
    policy_hash: str
    response_format: dict[str, str]
    max_tokens: int


@dataclass(frozen=True, slots=True)
class ParsedLLMModerationResponse:
    decision: Literal["accept", "reject"]
    moderation_category: str
    confidence: float
    short_reason: str
    rationale: str


class InvalidLLMModerationResponseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def keyword_filter(text: str, keywords: list[str]) -> FilterResult:
    """Keyword hits are stealth moderation blocks with no matched keyword stored."""
    for keyword in keywords:
        keyword = str(keyword)
        if keyword and keyword in text:
            return FilterResult(blocked=True, source="keyword", reason="keyword")
    return FilterResult(blocked=False)


def llm_policy_for(settings: Any, owner: str, qtype: str) -> LLMModerationPolicy | None:
    """Return typed LLM policy only when global and owner/type enablement both opt in."""
    llm_moderation = getattr(settings, "llm_moderation", None)
    if llm_moderation is None:
        return None
    return cast("LLMModerationPolicy | None", llm_moderation.policy_for(owner, qtype))


def build_llm_moderation_prompt(policy: LLMModerationPolicy, submission_text: str) -> LLMModerationPrompt:
    """Construct the provider-ready prompt boundary without secrets or requester metadata."""
    policy_hash = _llm_policy_hash(policy)
    example_output = json.dumps(
        {
            "decision": "reject",
            "moderation_category": "harassment",
            "confidence": 0.92,
            "short_reason": "Harassing or abusive submission",
            "rationale": "The submission targets a person with abusive language.",
        }
    )
    additive_policy = policy.policy_prompt.strip() or "No additional owner/question-type policy."
    system_policy = (
        "You moderate AQBox owner console submissions before they enter the review queue. "
        "Apply site-wide privacy rules and classify the moderation category using only these categories: "
        "safe, privacy, doxxing, identity_speculation, harassment, threats, spam, explicit_sexual_content, "
        "fan_drama, other. Treat doxxing, identity speculation, harassment, threats, spam, explicit sexual content, "
        "fan drama, and other policy abuse as reasons to reject. Use project terms consistently: submission, asker, "
        "owner console, question type, review queue, and moderation category."
    )
    output_contract = (
        "Return json only, as one strict JSON object with exactly these fields: decision, moderation_category, "
        "confidence, short_reason, rationale. decision must be accept or reject. confidence must be a number from "
        "0.0 to 1.0. short_reason is a safe owner-list reason and must not quote the submission. Example JSON object: "
        f"{example_output}"
    )
    owner_policy = (
        f"Additional owner/question-type policy: owner {policy.owner!r}, question type {policy.question_type!r}: {additive_policy}"
    )
    user_content = f"Moderate this submission from an asker for the owner console.\n<<<QUESTION>>>\n{submission_text}\n<<<END_QUESTION>>>"
    return LLMModerationPrompt(
        messages=[
            {"role": "system", "content": system_policy},
            {"role": "system", "content": output_contract},
            {"role": "system", "content": owner_policy},
            {"role": "user", "content": user_content},
        ],
        prompt_version=LLM_MODERATION_PROMPT_VERSION,
        policy_hash=policy_hash,
        response_format={"type": "json_object"},
        max_tokens=policy.max_tokens,
    )


def parse_llm_moderation_response(
    *,
    finish_reason: str,
    content: str | None,
    original_text: str | None = None,
) -> ParsedLLMModerationResponse:
    if finish_reason != "stop":
        raise InvalidLLMModerationResponseError("non_stop_finish_reason", f"LLM response finished with {finish_reason!r}")
    if content is None or not content.strip():
        raise InvalidLLMModerationResponseError("empty_content", "LLM response content was empty")
    try:
        parsed = json.loads(content, parse_constant=_reject_json_constant, object_pairs_hook=_strict_json_object_pairs)
    except ValueError as exc:
        raise InvalidLLMModerationResponseError("invalid_json", "LLM response content was not strict JSON") from exc
    if not isinstance(parsed, dict):
        raise InvalidLLMModerationResponseError("non_json_object", "LLM response content must be a JSON object")
    if not parsed:
        raise InvalidLLMModerationResponseError("missing_field", "LLM response object was empty")
    extra_fields = set(parsed) - _LLM_RESPONSE_FIELDS
    if extra_fields:
        raise InvalidLLMModerationResponseError("extra_field", f"LLM response included unsupported fields: {sorted(extra_fields)}")
    missing_fields = _LLM_RESPONSE_FIELDS - set(parsed)
    if missing_fields:
        raise InvalidLLMModerationResponseError("missing_field", f"LLM response was missing fields: {sorted(missing_fields)}")

    decision = parsed["decision"]
    if not isinstance(decision, str):
        raise InvalidLLMModerationResponseError("schema_mismatch", "LLM response decision must be a string")
    if decision not in {"accept", "reject"}:
        raise InvalidLLMModerationResponseError("invalid_decision", "LLM response decision must be accept or reject")
    moderation_category = parsed["moderation_category"]
    if not isinstance(moderation_category, str):
        raise InvalidLLMModerationResponseError("schema_mismatch", "LLM response moderation_category must be a string")
    if moderation_category not in LLM_MODERATION_CATEGORIES:
        raise InvalidLLMModerationResponseError("unknown_moderation_category", "LLM response moderation_category is not supported")

    confidence_raw = parsed["confidence"]
    if isinstance(confidence_raw, bool) or not isinstance(confidence_raw, int | float):
        raise InvalidLLMModerationResponseError("invalid_confidence", "LLM response confidence must be numeric")
    confidence = float(confidence_raw)
    if not isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
        raise InvalidLLMModerationResponseError("invalid_confidence", "LLM response confidence must be finite and between 0 and 1")

    short_reason = parsed["short_reason"]
    rationale = parsed["rationale"]
    if not isinstance(short_reason, str) or not isinstance(rationale, str):
        raise InvalidLLMModerationResponseError("schema_mismatch", "LLM response reasons must be strings")
    if not short_reason.strip() or not rationale.strip():
        raise InvalidLLMModerationResponseError("schema_mismatch", "LLM response reasons must be non-empty strings")
    if len(short_reason) > LLM_MODERATION_SHORT_REASON_MAX_LENGTH or len(rationale) > LLM_MODERATION_RATIONALE_MAX_LENGTH:
        raise InvalidLLMModerationResponseError("string_too_long", "LLM response reason text exceeded length limits")
    if original_text and _contains_original_submission_quote(short_reason, original_text):
        raise InvalidLLMModerationResponseError("unsafe_short_reason", "LLM response short_reason quoted the original submission")

    return ParsedLLMModerationResponse(
        decision=cast("Literal['accept', 'reject']", decision),
        moderation_category=moderation_category,
        confidence=confidence,
        short_reason=short_reason,
        rationale=rationale,
    )


def _llm_policy_hash(policy: LLMModerationPolicy) -> str:
    hash_input = {
        "prompt_version": LLM_MODERATION_PROMPT_VERSION,
        "owner": policy.owner,
        "question_type": policy.question_type,
        "policy_prompt": policy.policy_prompt,
        "high_confidence_reject_threshold": policy.high_confidence_reject_threshold,
        "review_all_model_rejects": policy.review_all_model_rejects,
    }
    payload = json.dumps(hash_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON constant {value}")


def _strict_json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key}")
        result[key] = value
    return result


def _contains_original_submission_quote(short_reason: str, original_text: str) -> bool:
    normalized_reason = " ".join(short_reason.lower().split())
    normalized_original = " ".join(original_text.lower().split())
    return bool(normalized_original and len(normalized_original) >= 12 and normalized_original in normalized_reason)


def purge_due_raw_audit_fields(db: Any, now_epoch: int) -> int:
    """Purge raw LLM payloads while retaining permanent moderation metadata."""
    if not getattr(db, "moderation_schema", False):
        return 0
    with db.lock:
        cur = db.conn.execute(
            """
            UPDATE question_moderation_audit
            SET raw_prompt = NULL,
                raw_request = NULL,
                raw_response = NULL,
                purged_at = ?
            WHERE purge_after IS NOT NULL
              AND purge_after <= ?
              AND purged_at IS NULL
            """,
            (now_epoch, now_epoch),
        )
        db.conn.commit()
        return int(cur.rowcount)
