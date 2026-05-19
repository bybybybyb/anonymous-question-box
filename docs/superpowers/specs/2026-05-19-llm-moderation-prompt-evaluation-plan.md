# Backend-Owned Moderation Policy, Hot-Reloadable Prompt YAML, And Historical Evaluation

## Summary

Refactor moderation so backend owns moderation categories, prompt wording, parser validation, and owner-console display wording. Frontend renders backend-provided `display_summary` / `display_detail` and removes local category/reason maps.

Split LLM runtime config from prompt policy. Main config keeps provider/runtime knobs and points to a separate hot-reloadable LLM prompt YAML. The prompt YAML defines a global baseline prompt plus optional per `owner/question_type` additive prompts. If global LLM moderation is enabled, new question types use the global prompt by default unless explicitly disabled.

## Key Changes

- Add a backend moderation catalog for `moderation_category`; reserve `safe` as non-removable and keep `accept <=> safe`.
- Drive prompt category list, category descriptions, examples, parser validation, display fallback text, policy hash, and tests from the catalog; bump prompt version from `aqbox-moderation-v4`.
- Add `llm_prompt_path` or equivalent in main config. Keep provider fields in `llm_filter`; move global and per-box prompt text to a separate YAML.
- Prompt YAML is hot-reloadable. Prompt changes affect newly queued/claimed moderation work without process restart.
- Prompt resolution order: global baseline, then matching `owner/question_type` additive prompt, with explicit per-type disable available.
- Record prompt version, prompt file hash, resolved policy hash, provider, model, and config hash on LLM moderation events.
- Backend returns stable per-row display fields. Existing raw moderation fields remain for compatibility/audit.

## Ops Visibility

- Keep public `/ops/health` non-sensitive: expose LLM enabled/running status, pending/due/locked counts, last check time, recent error class, prompt reload health, prompt version, and prompt/config hashes.
- Add or extend an authenticated ops endpoint for prompt text inspection, likely `/ops/config` or `/ops/llm/prompts`.
- Authenticated prompt ops output may include global prompt and resolved per `owner/question_type` prompt text, but must still redact API keys and avoid raw submission text.
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
- Generate candidate prompt YAML snippets per `owner/question_type`; never apply them automatically.
- Offline replay runs prompt build, provider call, parser, threshold/review decision, and display formatting.
- Replay requires explicit provider-egress opt-in, rate limit, cost cap, resume file, and no raw stdout.

## False-Positive Evaluation

- Control frame is owner-normal-visible submissions: `deleted_at IS NULL AND (no moderation state OR status = approved)`.
- Use traffic-weighted sampling plus minimum per `owner/question_type` quotas.
- Stratify when possible by time window, text length bucket, and answer status.
- Report "control rejection rate," not confirmed false-positive rate, unless manual review labels are added.
- Include counts, denominators, parser-invalid rate, category distribution, and would-enter-review outcome.

## Test Plan

- Backend tests cover catalog-driven prompt text, parser validation, `safe` invariants, policy hash changes, display fields, prompt YAML resolution, hot reload, and ops redaction/auth boundaries.
- Frontend tests/smoke verify review queue and detail modal render backend display fields without local maps.
- Analysis tests use temp SQLite fixtures for deleted rows, blocked rows, visible controls, missing columns, stale owner/type buckets, and representative sampling.
- Replay tests use a fake provider for batching, resume, invalid outputs, decision framing, and read-only DB access.
- Verify with `uv run pytest -q`, `uv run ruff check backend`, `uv run ruff format --check backend`, `uv run mypy backend/aqbox`, then frontend lint/build.

## Assumptions

- Full prompt text is authenticated ops data, not public health data.
- "Category" means `moderation_category`; grouping uses `owner/question_type bucket`.
- Raw production text stays only in git-ignored local artifacts, never logs, commits, CI artifacts, or ops responses.
- Browser smoke remains deterministic fixture coverage; full historical replay is backend offline tooling.
