# No Runtime Moderation Categories

## Status

Accepted.

## Context

The current LLM moderation scaffold asks the model for `moderation_category` and stores category values on moderation state/events. The prompt evaluation redesign removes runtime content taxonomy for v1: moderation mechanics are represented by stable machine `source/reason` values, while owner-facing explanation comes from validated `short_reason` / `rationale` or backend display fallbacks.

## Decision

Do not keep `moderation_category` in the v1 parser, API, storage, or frontend display contract. LLM output contains `decision`, `confidence`, `short_reason`, and `rationale`; every valid model rejection maps to `source=llm`, `reason=model_reject`. Operational failures use specific `source=llm_error` reasons. Historical analysis may discover risk patterns for prompt wording, but those patterns are not runtime categories unless a future ADR promotes them.
