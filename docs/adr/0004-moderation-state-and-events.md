# Moderation State and Events

## Status

Accepted.

## Context

The legacy moderation behavior used `question.deleted_at` for keyword moderation and later design notes proposed question-level moderation columns plus `question_moderation_audit`. The moderation redesign separates owner deletion from moderation decisions: `deleted_at` remains an owner/manual deletion timestamp, while moderation visibility and history need their own storage.

Async LLM moderation also introduces states that are not deletions. A submission can be pending provider review, blocked for owner review, approved after review, or accepted without any moderation state row. Provider failures and timeouts should not silently accept content; the redesign intentionally moves those cases to owner review.

## Decision

Use dedicated moderation tables:

- `question_moderation_state` stores the current projection for submissions that are `pending`, `blocked`, or `approved`.
- `question_moderation_event` stores append-only moderation history, including keyword blocks, LLM decisions, owner approvals, and moderation-relevant owner deletions.

Normal accepted submissions have no state row. Approved rows keep state so the owner console can show that they passed review. Owner deletion continues to set `question.deleted_at`; it records a moderation event only when the submission already has moderation state.

LLM moderation is asynchronous. LLM-enabled submissions enter `pending` state and are hidden from owner normal lists, review queues, owner detail, and live views until resolved. Provider rejects go to owner review, and timeout/max-attempt/config failures also fail to review as `blocked` with an explicit LLM error reason.

## Consequences

The owner console and repository queries must treat moderation visibility separately from deletion visibility. Asker reads preserve legacy access even when owner deletion or moderation state exists.

The old `question.moderation_*` scaffold and `question_moderation_audit` table remain historical/deprecated until a deliberate cleanup migration. New moderation behavior should use state/event tables and avoid storing matched keyword text by default.

Ops and audit records should store provider/model, prompt/config hashes, thresholds, and reason metadata for LLM decisions. Raw prompts, requests, responses, and question text must not appear in ops surfaces; any raw event retention must be explicit and purgeable.
