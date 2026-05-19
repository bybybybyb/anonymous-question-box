# Backend-Owned Moderation Policy, Hot-Reloadable Prompt YAML, And Historical Evaluation

## Summary

Refactor moderation so backend owns prompt wording, parser validation, machine source/reason semantics, and owner-console display wording. Frontend renders backend-provided `display_summary` / `display_detail` and removes local category/reason maps.

Split LLM runtime config from prompt policy. Main config keeps provider/runtime knobs and points to a separate hot-reloadable LLM prompt YAML. The prompt YAML defines a global baseline prompt plus optional per `owner/question_type` additive prompts. If global LLM moderation is enabled, new question types use the global prompt by default unless explicitly disabled.

## Key Changes

- Remove `moderation_category` as a required v1 runtime parser/API concept.
- New LLM parser output should require only `decision`, `confidence`, `short_reason`, and `rationale` for both accept and reject decisions. `decision=reject` maps to machine `source=llm` and `reason=model_reject`; provider/parser failures map to `source=llm_error` with stable machine reasons.
- Every valid `decision=reject` enters owner review regardless of confidence. `confidence` is recorded for audit/debug/tuning only in v1; it does not change review behavior.
- Keep `confidence` required and bounded between `0.0` and `1.0` even though it is audit-only.
- Valid LLM accept removes/clears the current pending moderation state so the submission behaves like a normal accepted row, while still recording an event for audit. Valid LLM reject becomes `blocked`; owner approval of a blocked row becomes `approved`.
- Do not ask the LLM for machine reason codes in v1. Every model rejection maps to `source=llm`, `reason=model_reject`; semantic nuance belongs in `short_reason` and `rationale`.
- Prompt policy may describe natural-language risk patterns such as privacy exposure, spam, abuse, threats, or owner-visible risk, but the output contract stays label-free and does not ask the model to emit a taxonomy.
- Validate LLM-provided `short_reason` and `rationale` aggressively before owner display: non-empty strings, bounded length, concise summary, Simplified Chinese, and no quoted submission text or repeated sensitive tokens such as emails, phones, URLs, handles, or long private substrings. Invalid reason text makes the provider response invalid and moves the row through `llm_error/invalid_response`.
- Backend `display_summary` / `display_detail` prefer validated LLM `short_reason` / `rationale` for `source=llm, reason=model_reject`; operational errors, manual rows without explicit text, and any missing text use backend fallback text keyed by `source/reason`.
- Backend may still return raw `short_reason` / `rationale` in the moderation object for audit/debug/analysis, but frontend rendering must use only `display_summary` / `display_detail` and remove local category/reason fallback maps.
- Approved rows keep moderation display fields in owner APIs for audit/context, but normal-list UI should render this subtly, such as a reviewed badge or detail-only metadata rather than full review text.
- Use specific stable `llm_error` reasons for ops/debugging, such as `config_disabled`, `provider_timeout`, `invalid_response`, `max_attempts_exhausted`, and `rate_limited`. These are operational failure classes, not content categories; owner-facing display may collapse them to the same safe fallback wording.
- Remove existing `moderation_category` storage/API/parser usage before merge, before new production moderation data is created. This is the first implementation cleanup, not deferred compatibility work.
- Remove `moderation_category` storage with a new named migration rather than editing existing migration history.
- Add a backend-owned display fallback catalog keyed by machine `source/reason`, with safe owner-console fallback text and tests.
- Define allowed moderation `source/reason` and deletion `source/reason` values in backend code as the parser/API/test contract. Keep `CONTEXT.md` limited to the domain concepts, not implementation enum lists.
- Add `llm_prompt_path` or equivalent in main config. Keep provider fields in `llm_filter`; move global and per-box prompt text to a separate YAML.
- Commit an example prompt YAML such as `backend/config/llm-prompts.example.yaml`; keep real local prompt files untracked unless explicitly intended for deployment.
- Prompt YAML v1 schema: required semantic-version-style `version` such as `0.1.0`; required non-empty `global.risk_policy` when LLM is enabled; optional `overrides` list with exact `owner`, `question_type`, and additive text. It has no provider/model/API key, no thresholds, no enable/disable flags, no wildcard overrides, and no baseline replacement.
- Historical data analysis should discover potential risk patterns the final prompts need to cover, such as spam, abuse, privacy exposure, threats, and owner-specific risks. It should not produce runtime categories or clustering outputs.
- Prompt YAML is hot-reloadable policy wording only and cannot redefine machine `source/reason` semantics.
- Prompt YAML is hot-reloadable. Prompt changes affect newly queued/claimed moderation work without process restart.
- Prompt YAML startup failure should fail startup when LLM moderation is enabled and no last-good prompt exists. Hot-reload parse failures keep the last-good prompt active, mark prompt reload unhealthy in ops surfaces, and expose last-good prompt metadata plus the latest error class.
- When global LLM moderation is enabled, prompt YAML must load and the global risk policy must be non-empty. When LLM moderation is disabled, prompt YAML absence or emptiness should not block startup.
- Prompt resolution order: global baseline, then matching `owner/question_type` additive prompt. Owner/type prompt text is additive-only in v1; it cannot replace or bypass the global risk baseline.
- Prompt YAML overrides for unknown owners/question types should not fail parsing or hot reload. Runtime resolution ignores them, and authenticated ops/config reports them as warnings so typos and stale overrides are visible.
- Duplicate prompt YAML overrides for the same `owner/question_type` are parse errors; combine multiple paragraphs into one additive block instead of relying on resolution order.
- Prompt YAML supports exact `owner/question_type` additive overrides only in v1. Do not add wildcard owner/type precedence rules unless scale later justifies them.
- Pending moderation jobs resolve prompt/main config at worker claim time, not submit time. Each provider attempt uses the prompt/config snapshot assembled before that call and records the prompt/config hashes actually used.
- Main runtime config owns explicit per-type disable, including test/smoke-only disables; prompt YAML owns wording, not whether moderation runs.
- When a question type is explicitly disabled in main config, submissions for that type bypass LLM moderation entirely and create no moderation state/event.
- If global LLM moderation is disabled while rows are already pending, the worker should move claimed pending rows to review as `source=llm_error`, `reason=config_disabled`, rather than leaving them hidden or auto-approving them.
- Record prompt version, prompt file hash, resolved policy hash, provider, model, and config hash on LLM moderation events.
- `prompt_file_hash` identifies the loaded prompt YAML file content. `policy_hash` identifies the resolved non-secret moderation policy used for a specific decision, including output-contract text, global prompt, matched additive prompt, and display fallback catalog version. Use these hashes to group/debug behavior changes without exposing raw prompt or submission text in normal ops surfaces.
- Backend returns stable per-row display fields. Existing raw moderation fields remain for compatibility/audit.

## Ops Visibility

- Keep public `/ops/health` non-sensitive: expose LLM enabled/running status, pending/due/locked counts, last check time, recent error class, prompt reload health, prompt version, and prompt/config hashes.
- Public `/ops/health` should expose only short prompt/config/policy hash prefixes or omit hashes when detail is unnecessary. Authenticated ops may expose full hashes for exact debugging.
- Add or extend an authenticated ops endpoint for prompt text inspection, likely `/ops/config` or `/ops/llm/prompts`.
- Authenticated prompt ops output may include global prompt and resolved per `owner/question_type` prompt text, but must still redact API keys and avoid raw submission text.
- Authenticated prompt inspection is allowed for active prompt YAML version/hash, global baseline text, resolved prompt for a specific `owner/question_type`, matched additive prompt, last reload error class, and last-good metadata. It must never include API keys, raw submissions, or raw provider request/response bodies.
- Health/config should report prompt YAML parse errors and last-good prompt metadata so hot reload failures are visible without taking the service down.

## Production Data Workflow

- Use runbook paths: host alias `tc`, prod DB `/root/anonymous_qbox.db`, prod config `/root/aqbox-releases/5c3d6a8/backend/config/config.yaml`.
- Pull DB as a consistent SQLite snapshot to `test/anonymous_qbox_prod.db` using SQLite backup or WAL-safe equivalent.
- Pull or inspect production config read-only, redacting secrets.
- Add `test/moderation_analysis/` to ignored local artifacts before generating raw reports.
- Analysis uses direct read-only SQLite and tolerates missing newer columns/tables.

## Analysis And Replay

- Treat `deleted_at IS NOT NULL` as historical deletion data, not ground-truth unsafe content.
- Split deleted rows by evidence strength: `keyword`, `owner_manual`, `legacy_unknown`.
- Include current blocked rows separately by `source/reason`; exclude or separately report `llm_error/never_evaluated`.
- Category discovery uses owner-deleted submissions, keyword soft-deleted submissions, and owner-visible control submissions as evidence buckets, not ground truth labels. Owner deletion is the strongest owner-intent signal; keyword deletion reflects past rule configuration; visible controls protect against overfitting normal audience language.
- Pending rows, `llm_error/never_evaluated`, and legacy-unknown rows should be excluded from prompt risk-pattern discovery or reported separately. Raw IP/geo metadata should not shape prompt policy unless the text itself raises a privacy issue.
- Run historical data analysis to improve prompt risk coverage and owner/type additive prompt wording. Do not treat the current hardcoded categories as sticky.
- Baseline prompt risk-pattern discovery is local/read-only and deterministic. Optional LLM-assisted risk summarization is allowed only behind explicit provider-egress opt-in with rate limiting, cost cap, resume file, git-ignored local outputs, and no raw submission text on stdout.
- LLM-assisted risk summarization uses separate analysis-only provider/model/API-key settings, not the live `llm_filter` runtime config. Offline analysis may choose a different model than production moderation.
- Analysis produces a manual review report over sampled historical evidence: likely global risk patterns, owner/type-specific risks, visible-control language that should remain accepted, and paraphrased examples. It may include candidate prompt YAML snippets per `owner/question_type`, but never applies them automatically.
- Offline replay runs prompt build, provider call, parser, threshold/review decision, and display formatting.
- Replay requires explicit provider-egress opt-in, rate limit, cost cap, resume file, and no raw stdout.

## False-Positive Evaluation

- Control frame is owner-normal-visible submissions: `deleted_at IS NULL AND (no moderation state OR status = approved)`.
- Use traffic-weighted sampling plus minimum per `owner/question_type` quotas.
- Stratify when possible by time window, text length bucket, and answer status.
- Report "control rejection rate," not confirmed false-positive rate, unless manual review labels are added.
- Include counts, denominators, control rejection rate, deleted/manual evidence rejection rate, parser-invalid rate, `llm_error` rate by class, source/reason distribution, would-enter-review counts by `owner/question_type`, sampled reason quality, and prompt risk-pattern coverage notes. Do not rely on category distribution.

## Test Plan

- Backend tests cover source/reason parser validation, display fallback fields, policy hash changes, prompt YAML resolution, hot reload, and ops redaction/auth boundaries.
- Frontend tests/smoke verify review queue and detail modal render backend display fields without local maps.
- Analysis tests use temp SQLite fixtures for deleted rows, blocked rows, visible controls, missing columns, stale owner/type buckets, and representative sampling.
- Replay tests use a fake provider for batching, resume, invalid outputs, decision framing, and read-only DB access.
- Verify with `uv run pytest -q`, `uv run ruff check backend`, `uv run ruff format --check backend`, `uv run mypy backend/aqbox`, then frontend lint/build.

## Implementation Checklist

1. Add a new named migration to remove `moderation_category` storage, and remove parser/API/frontend dependencies on category.
2. Define backend `source/reason` constants and a display fallback catalog.
3. Change the LLM parser contract to `decision`, `confidence`, `short_reason`, and `rationale`.
4. Serialize `display_summary` / `display_detail`; update frontend rendering to use only display fields.
5. Split prompt YAML from main runtime config. Main config keeps provider/runtime knobs, global enablement, per-type disables, and `llm_prompt_path`.
6. Implement prompt hot reload, last-good prompt behavior, ops health, and authenticated prompt inspection.
7. Update replay/evaluation tooling to category-free metrics and prompt risk-pattern reports.
8. Run backend tests/ruff/mypy, then frontend lint/build/smoke.

## Assumptions

- Full prompt text is authenticated ops data, not public health data.
- Avoid using "category" for runtime moderation; grouping uses `owner/question_type bucket`, and moderation mechanics use machine `source/reason`.
- Project scale is small enough that LLM moderation uses one global enablement switch: when global LLM moderation is enabled, all configured question types use the global prompt by default unless explicitly disabled.
- Explicit per-type disable belongs in main runtime config, not prompt YAML, because it affects cost, latency, visibility, and test fixture behavior rather than prompt wording.
- This implementation can treat the moderation policy/display system as new work: do not add backfill or backward-compatibility paths unless explicitly requested.
- There is no need to preserve `moderation_category` for existing data; remove it before this PRD/plan merges into implementation.
- Raw production text stays only in git-ignored local artifacts, never logs, commits, CI artifacts, or ops responses.
- Browser smoke remains deterministic fixture coverage; full historical replay is backend offline tooling.
