# Moderation State and Events

## Status

Accepted.

## Context

The legacy moderation behavior used `question.deleted_at` for keyword moderation and later design notes proposed question-level moderation columns plus `question_moderation_audit`. The moderation redesign keeps the legacy keyword stealth-delete contract while separating LLM/manual review from deletion: keyword matches use `deleted_at`, while reviewable moderation visibility and history use their own storage.

Async LLM moderation also introduces states that are not deletions. A submission can be pending provider review, blocked for owner review, approved after review, or accepted without any moderation state row. Provider failures and timeouts should not silently accept content; the redesign intentionally moves those cases to owner review.

## Decision

Use dedicated moderation tables:

- `question_moderation_state` stores the current projection for LLM/manual review submissions that are `pending`, `blocked`, or `approved`.
- `question_moderation_event` stores append-only LLM/manual moderation history, including LLM decisions, owner approvals, and moderation-relevant owner deletions.

Normal accepted submissions have no state row. Keyword-filtered submissions also have no state row: they are inserted with `question.deleted_at = asked_at` and `question.deletion_source = "keyword"`, return legacy submit success, remain asker-readable, and stay hidden from owner normal lists, review queues, owner detail, and live views. Approved rows keep state so the owner console can show that they passed review. Owner deletion continues to set `question.deleted_at` and now records `question.deletion_source = "owner_manual"` for both normal and moderated rows; it records a moderation event only when the submission already has moderation state.

LLM moderation is asynchronous. LLM-enabled submissions enter `pending` state and are hidden from owner normal lists, review queues, owner detail, and live views until resolved. Provider rejects go to owner review, and timeout/max-attempt/config failures also fail to review as `blocked` with an explicit LLM error reason.

## Consequences

The owner console and repository queries must treat reviewable moderation visibility separately from deletion visibility while preserving keyword stealth-delete as a deletion-backed legacy behavior. Asker reads preserve legacy access even when owner deletion, keyword soft-delete, or moderation state exists.

The old `question.moderation_*` scaffold and `question_moderation_audit` table remain historical/deprecated until a deliberate cleanup migration. New LLM/manual moderation behavior should use state/event tables. Keyword filtering should not create moderation state/events and should avoid storing matched keyword text by default.

Ops and audit records should store provider/model, prompt/config hashes, thresholds, and reason metadata for LLM decisions. Raw prompts, requests, responses, and question text must not appear in ops surfaces; any raw event retention must be explicit and purgeable.
