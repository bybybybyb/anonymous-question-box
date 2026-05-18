# Moderation Redesign Plan

> **Status:** Planning artifact for `codex/moderation-redesign`.
> **Base:** `origin/main` at merge commit `905ebf4`.
> **Final grill:** Incorporated after read-only `grill-with-docs` review on 2026-05-18.

## Summary

Implement moderation in three slices: first a small owner-console refactor, then keyword moderation using dedicated tables, then async LLM moderation.

Retire "soft-delete" as moderation language. Use:

- **Moderation block** for keyword/LLM hiding.
- **Review queue** for owner-visible moderation review work.
- **Owner deletion** for `question.deleted_at`.

`deleted_at` remains an owner/manual deletion field. Moderation visibility moves to `question_moderation_state`; moderation history moves to `question_moderation_event`.

Latest `origin/main` includes the Python backend refactor, migration runner, WAL/busy-timeout setup, tighter owner mutation guards, and frontend cleanup. This plan builds on that shape.

## Grill Resolutions

1. Accept: retire moderation "soft-delete" language; update glossary/docs.
2. Accept with nuance: preserve the legacy contract doc as history, but add a superseded-by-redesign note.
3. Accept: add an ADR for dedicated moderation state/event tables.
4. Accept: register `0004_moderation_state_events` unconditionally; keyword moderation needs it without `llm_filter`.
5. Accept: leave `0003_moderation_scaffold` in place and unused for now; do not rewrite migration history.
6. Accept: normal accepted submissions have no state row; approved rows keep state indefinitely unless deleted.
7. Accept: do not store matched keyword text by default.
8. Accept: owner deletion creates a moderation event only when deleting a row that already has moderation state.
9. Accept: owner deletion still does not revoke asker read access.
10. Accept with better framing: normal owner list can remain card-based, but the moderation surface should be a dedicated review table.
11. Accept: missing `moderation_status` defaults to `normal`.
12. Accept: `LiveView.vue` must always use normal moderation visibility.
13. Accept: pending LLM rows are hidden from owner detail until resolved.
14. Accept: blocked submissions may be answered without approval; answering does not approve.
15. Accept: mark/unmark may work on blocked non-deleted rows at API level, but review table does not expose mark controls.
16. Accept: approval is idempotent for already-approved rows and otherwise only allows `blocked -> approved`.
17. Accept: return moderation counts for tab/table badges.
18. Accept: location options and counts must respect moderation status.
19. Accept: review table may show owner/admin metadata such as IP/location before text reveal; only question text is hidden.
20. Accept: invalid `moderation_status` fails with a legacy-shaped `400`.
21. Accept: use a provider-generic OpenAI-compatible LLM interface; DeepSeek is the first adapter/default.
22. Accept: async LLM fail-to-review is an explicit policy shift from old sync fail-open spec and should be documented.
23. Accept with better framing: API may use `blocked`, but UI should say "review queue" / `审核队列`.
24. Accept: raw LLM prompt/request/response, when enabled, live in `question_moderation_event` with purge fields.
25. Accept: package upgrades should be adjacent prep or an isolated first commit, not mixed into moderation behavior.

## Grill Context

The final `grill-with-docs` pass challenged the plan against existing code, docs, and domain language. The important context behind the resolutions:

| # | Challenge | Repo facts / tension | Decision |
| --- | --- | --- | --- |
| 1 | Should "soft-delete" be retired for moderation? | `CONTEXT.md`, `AGENTS.md`, and `docs/contract/go-api-behavior.md` define keyword moderation as soft-delete, but the redesign makes `deleted_at` owner deletion only. | Retire moderation soft-delete language; introduce **Moderation block** and **Owner deletion**. |
| 2 | Should the Go contract doc be rewritten or preserved? | `docs/contract/go-api-behavior.md` is a historical parity catalog and accurately describes old Go/Python behavior. | Preserve history; add a superseded-by-redesign note instead of silently rewriting old behavior. |
| 3 | Does dedicated moderation state/event storage merit an ADR? | `0003_moderation_scaffold` already created question-level moderation columns and an audit table; the redesign rejects that path. | Add an ADR for `question_moderation_state` + `question_moderation_event`. |
| 4 | Should the new moderation migration run only when LLM config exists? | Keyword moderation needs the tables even when `llm_filter` is absent; current migration runner registers migrations centrally. | Register `0004_moderation_state_events` unconditionally. |
| 5 | What happens to the existing moderation scaffold? | `migrate_moderation()` creates `question.moderation_*` and `question_moderation_audit`; `purge_due_raw_audit_fields()` targets the old audit table. | Leave scaffold in place and unused; move raw purge support to events during the LLM slice. |
| 6 | Should accepted submissions have state rows? | Current list queries are simple around `question`; approved overrides need persistent history but clean submissions do not. | No state row means normal/unmoderated; approved rows retain state. |
| 7 | Should keyword blocks store matched keyword text? | Existing keyword filter returns only source/reason, and the old LLM spec avoids exposing keyword lists/matched text. | Do not store matched keyword by default. |
| 8 | Should every owner delete create a moderation event? | Existing delete is a submission lifecycle action; normal deletion is not a moderation decision. | Record delete events only for submissions that already have moderation state. |
| 9 | Should owner deletion revoke asker read access? | `SubmissionService.get_for_asker()` reads with `include_deleted=True`; this is existing legacy behavior. | Preserve asker readability for owner-deleted submissions. |
| 10 | Should the moderated UI be cards or table? | Existing owner list is card-preview-first; moderation review needs compact metadata/actions with hidden text. | Keep normal list card-based; add a dedicated review table. |
| 11 | What is the default when `moderation_status` is omitted? | `OwnerView.vue` and `LiveView.vue` already call `/owner/questions`; smoke tests depend on unchanged default behavior. | Missing `moderation_status` defaults to `normal`. |
| 12 | Should live mode show blocked or pending rows? | Live mode projects and can answer/display submissions; moderation-hidden content should never enter that flow. | LiveView always uses normal visibility. |
| 13 | Should owner detail return pending LLM rows? | Pending rows are intentionally hidden until resolved; detail behavior was previously unspecified. | Owner detail returns 404 for pending rows. |
| 14 | Can blocked submissions be answered? | Current answer route works by UUID for non-deleted rows; product decision allows answering without approval. | Allow answering blocked rows; answering does not approve. |
| 15 | Should mark/unmark work on blocked rows? | Current `update_mark()` only excludes `deleted_at`; the UI decision is only to hide mark controls in review. | Backend may mark non-deleted blocked rows; review table does not expose it. |
| 16 | Is approval idempotent? | New route still needs legacy-shaped errors; state transitions must be predictable. | Already-approved returns success; only blocked can transition to approved. |
| 17 | Should list responses include moderation counts? | Tabs need counts without fetching both lists; earlier plan had dropped count language. | Return `moderation_counts`, at least blocked count. |
| 18 | Should geo location options respect moderation state? | `list_location_options()` currently filters only `deleted_at`; otherwise hidden rows would affect normal location filters. | Location options/counts must use the same moderation status as the active list. |
| 19 | Should review rows show IP/location before text reveal? | Owner/admin routes may expose IP; the privacy/harm concern is question content preview. | Show owner metadata; hide only question text by default. |
| 20 | How should invalid `moderation_status` behave? | Legacy routes must not leak FastAPI 422; parser can wrap validation failures. | Return legacy-shaped 400. |
| 21 | Should LLM integration be DeepSeek-specific? | Old spec is DeepSeek-specific, but new plan stores provider/model metadata and says LLM moderation. | Use provider-generic OpenAI-compatible interface; DeepSeek first. |
| 22 | Should async LLM fail open or fail to review? | Old DeepSeek spec says sync fail-open; new plan sends timeout/max failure to review. | Explicitly supersede old fail-open table with async fail-to-review. |
| 23 | Does `blocked` overstate `llm_error` / low-confidence rows? | API has one blocked/reviewable state; UI label can shape owner expectation. | Keep API `blocked`, label UI as **Review queue** / `审核队列`. |
| 24 | Where should raw LLM prompt/request/response live? | Old audit table modeled raw purge, but event table now owns moderation history. | Store raw event fields only when config enables retention; purge event fields. |
| 25 | Should package upgrades be mixed into moderation work? | Dependency lockfile churn can obscure moderation behavior changes. | Keep package upgrades adjacent or isolated from moderation implementation. |

## Slice 3 Grill Follow-Up Context

The Slice 3 refinement grill focused on turning "async LLM moderation" into implementation-ready boundaries. The accepted refinements:

- Concede, with product choice changed: keep `llm_filter` hot-reloadable, and record the exact config/prompt/provider facts used when the worker actually processes a row.
- Require both global and per owner/question-type opt-in; missing per-type policy remains disabled even if the global provider is configured.
- Add worker-only schema with a new `0005_llm_moderation_worker_fields` migration; do not rewrite `0004_moderation_state_events`.
- Never hold `Database.lock` across provider I/O; use short DB transactions for claiming/finalizing work.
- Add an atomic `insert_pending_question(...)` path for question insert + pending state + queued event.
- Treat `reason` as a stable machine code; store/display `short_reason`, `rationale`, `confidence`, provider, model, prompt version, and policy/config hashes separately.
- Route every model `reject` to owner review; use `high_confidence_reject_threshold` only to distinguish `llm` from `llm_low_confidence`, unless the config later adds an explicit auto-approve-on-low-confidence behavior.
- Prompt in project terms: submission, asker, owner console, question type, moderation category.
- Only a strict, non-empty JSON object with acceptable schema and `finish_reason = "stop"` can produce a moderation decision.
- Use `httpx.AsyncClient` behind a provider-generic boundary; classify errors as config/auth, rate limited, timeout, network, server, invalid response, or quota/circuit cap.
- Expose moderation worker state in `/ops/health` when LLM is enabled; never expose secrets or raw prompt text in ops/logs.
- Replace the old raw audit purge helper with an event-field purge helper.
- Keep real DeepSeek tests opt-in behind both `AQBOX_RUN_DEEPSEEK_INTEGRATION=1` and `DEEPSEEK_API_KEY`.
- Update docs/ADR before Slice 3 code so old sync/fail-open DeepSeek language cannot mislead implementers.

### Hot-Reload Decision Context

The grill initially argued for making all `llm_filter` changes restart-required, because a queued moderation job can otherwise be submitted under one policy and processed under a newer one. That is a real nondeterminism risk, but the product/ops decision is to accept it in exchange for being able to adjust policy prompts, thresholds, provider settings, and temporary disables without restarting the service.

This is consistent with the rest of the owner-config experience: AQBox already treats config as an operational control surface, not a compiled deployment artifact. LLM moderation should behave the same way unless a setting truly changes process wiring or persistent storage shape. The important requirement is therefore not enqueue-time determinism; it is auditability of what actually happened.

Implementation implications:

- The current backend still lists `llm_filter` in `SettingsProvider.RESTART_REQUIRED_FIELDS`; Slice 3 must remove or narrow that restart-required treatment when typed LLM config lands.
- The worker must read current settings at claim/evaluation time, not cache one startup snapshot forever.
- The submit path may enqueue based on the current config, but the worker is allowed to re-check current config before calling the provider.
- If config changes between submit and worker claim, the event should make that visible by recording config hash/version, policy hash, prompt version, provider, model, and thresholds used for the actual decision.
- If LLM is disabled after rows are already pending, the worker should use the current config decision path when claiming them. The first v1 behavior is to move such rows into review as `llm_error/never_evaluated` or another explicit config-disabled reason, rather than silently accepting or deleting them.
- If policy text or thresholds change while a provider call is in flight, only the claimed attempt uses the policy snapshot assembled for that call. The finalize step records that snapshot facts.
- If API key/base URL/model is changed, new claims use the new values; in-flight calls finish or time out with the old values.
- Hot reload does not excuse leaky observability: `/ops/config`, `/ops/health`, logs, and moderation events must never expose API keys or raw prompt/question text unless raw retention is explicitly enabled for the event table.

Rejected alternative:

- Freeze the full LLM policy at enqueue time and store it with the pending row. This would make replay/debugging more deterministic, but it increases raw policy retention, complicates key rotation/provider rollout, and fights the operator goal of "current config controls current behavior." We instead store hashes/versions plus provider/model/threshold facts, and only store raw prompt/request/response behind the explicit raw-retention setting.

## Prep TODOs

- Keep package cleanup separate from moderation behavior, either as an adjacent prep PR or an isolated first commit.
- Remove unused `snowpack`.
- Upgrade `vite` + `@vitejs/plugin-vue`, `vue` + `vue-router`, `axios`, `bootstrap`.
- Upgrade or remove `swiper` depending on image-support direction.
- Verify package cleanup with frontend lint/build/smoke.

## Slice 1: Owner UI Refactor

- Keep Vue 3 Options API, Bootstrap, and current routes.
- Refactor `OwnerView.vue` enough to support normal list plus moderation review table without duplicating request logic.
- Keep this refactor small: latest main already removed the stale Vue 2-era `Vue.extend(AnswerView)` block and fixed `/api` path consistency.
- Let `AnswerView.vue` render moderation metadata when present.
- Ensure missing `moderation_status` means `normal` so current owner and live flows keep working.
- Validate with existing owner smoke flow; smoke test is sufficient for this refactor slice.

## Slice 2: Keyword Moderation Tables

- Add a new named migration via the existing migration runner in `backend/aqbox/db.py`: `0004_moderation_state_events`.
- Register `0004_moderation_state_events` unconditionally in `_migrations()`.
- Add:
  - `question_moderation_state`: current projection for `pending`, `blocked`, `approved`.
  - `question_moderation_event`: append-only moderation history.
- Treat existing `0003_moderation_scaffold` columns/table as deprecated scaffold:
  - do not depend on `question.moderation_source`, `question.moderation_reason`, `question.moderated_at`, or `question_moderation_audit`;
  - do not remove them in this slice unless a separate cleanup migration is deliberately planned;
  - update or replace `purge_due_raw_audit_fields()` during the LLM slice, when raw retention moves to `question_moderation_event`.
- Normal accepted submissions have no moderation state row.
- Approved rows retain `question_moderation_state.status = "approved"` indefinitely unless the submission is owner-deleted.
- Keyword hits:
  - insert question with `deleted_at = NULL`;
  - create `blocked` state and event;
  - do both in one DB lock/transaction through a new repository/DB method, because current `insert_question()` commits immediately;
  - return legacy `200 {uuid, asked_at}`;
  - remain readable by asker.
- Do not store matched keyword text by default. Store `source=keyword`, `reason=keyword`, and optional category only.
- Existing historical `deleted_at` rows are not backfilled.
- Owner deletion still sets `question.deleted_at`; deleted rows disappear from normal and review queues but remain asker-readable under the existing token behavior.
- Deleting a submission with moderation state records a moderation event. Deleting a normal submission does not create a moderation event.

## State Visibility Matrix

| State | State row | Owner normal list | Review queue/table | Owner detail | Live view | Asker read |
| --- | --- | --- | --- | --- | --- | --- |
| Normal/unmoderated | none | Yes | No | Yes | Yes | Yes |
| Pending LLM | `pending` | No | No | No | No | Yes |
| Blocked/reviewable | `blocked` | No | Yes | Yes | No | Yes |
| Approved override | `approved` | Yes, with subtle badge | No | Yes, with moderation metadata | Yes | Yes |
| Owner-deleted | any/none + `deleted_at` | No | No | No | No | Yes, unchanged legacy behavior |

## API Behavior

- Extend `ListQuestionsRequest` and `POST /owner/questions` with `moderation_status: "normal" | "blocked"`.
- Missing `moderation_status` defaults to `"normal"`.
- Invalid `moderation_status` returns a legacy-shaped `400 {"error": "..."}`.
- Prefer `moderation_status` over existing unused `include_moderated` / `moderation_source`; those fields can remain ignored/deprecated for compatibility.
- Normal list mode returns unmoderated rows plus approved rows.
- Blocked mode returns reviewable blocked rows only.
- `POST /owner/questions` also returns `moderation_counts`, at least `moderation_counts.blocked`, computed under the same owner/type/day/reply/location filters where applicable.
- `list_location_options()` must respect `moderation_status`; normal options count normal rows only, blocked options count reviewable rows only.
- `GET /owner/questions/{uuid}` returns normal, approved, and blocked non-deleted submissions with moderation metadata when present.
- `GET /owner/questions/{uuid}` returns 404 for pending and owner-deleted submissions.
- Add `PUT /owner/questions/{uuid}/moderation/approve`.
- Approval semantics:
  - `blocked -> approved` succeeds and records an event.
  - already-approved rows return success idempotently.
  - pending, deleted, and unmoderated rows return legacy-shaped errors.
- Answering a blocked submission is allowed and does not approve it.
- Mark/unmark may remain allowed for any non-deleted row at the backend level, but the review table does not expose mark controls.

## Owner UI Behavior

- Normal owner list may stay card-based.
- Add a dedicated review queue/table for `moderation_status = "blocked"`, labeled as `审核队列` or equivalent rather than "blocked".
- Review table rows show:
  - moderation source/category/short reason;
  - submission time and answer status;
  - owner/admin metadata such as IP/location when available;
  - actions: reveal text preview, open detail, approve, delete.
- Review table rows hide question text by default.
- Revealing text is per-row and session-local.
- The review table does not expose mark/unmark.
- Approved rows return to the normal list with a subtle `已审核通过` badge.
- `LiveView.vue` must always use normal visibility and never show pending or blocked rows.

## Slice 3: Async LLM Moderation

- LLM moderation is async.
- Use a provider-generic OpenAI-compatible interface, with DeepSeek as the first adapter/default.
- LLM-enabled submissions create `pending` state and are hidden from normal/review/live/detail until resolved.
- Worker uses DB-backed pending rows with attempts/locks.
- Two attempts total; auth/config 4xx errors are non-retryable.
- High-confidence reject becomes `blocked/source=llm`.
- Low-confidence reject becomes `blocked/source=llm_low_confidence/reason=needs_review`.
- Timeout/max failure becomes `blocked/source=llm_error/reason=never_evaluated`.
- This fail-to-review behavior intentionally supersedes the old DeepSeek sync/fail-open spec.
- Accept clears the pending state row and stores an event only.
- Answering a blocked question remains allowed and still does not approve it.

### Slice 3 Detailed TODOs

#### 3.1 Configuration And Enablement

- Add typed config parsing for LLM moderation while keeping raw YAML backward-compatible:
  - global provider settings: provider name, base URL, model, timeout, max tokens, confidence thresholds, max attempts, backoff, raw-retention settings;
  - per owner/question-type opt-in and additive policy prompt;
  - API key resolution from environment first, config fallback only for local/dev.
- Require both global `llm_filter.enabled` and per owner/question-type `enabled: true`; keep missing or disabled policy disabled for that owner/type.
- Support empty additive policy text only when the per-type config is explicitly enabled; do not infer enablement from a provider key alone.
- Use a sample shape like:

```yaml
llm_filter:
  enabled: true
  provider: deepseek
  model: deepseek-v4-flash
  api_key_env: DEEPSEEK_API_KEY
  high_confidence_reject_threshold: 0.85
  review_all_model_rejects: true
  boxes:
    default:
      question_types:
        default:
          enabled: true
          policy_prompt: ""
```

- Add `/ops/config` redaction for any LLM API key material.
- Make `llm_filter` hot-reloadable in Slice 3 v1. Operators accept that pending rows may be processed under the config that is current at worker execution time, not necessarily the config that existed when the submission was queued.
- Remove or narrow `llm_filter` from `SettingsProvider.RESTART_REQUIRED_FIELDS`; do not leave the new typed LLM config stuck behind restart-required merge behavior.
- Record what was actually used on each queued/processed moderation event: settings version/config hash, prompt version, policy hash, provider, model, and relevant thresholds.
- If hot reload disables LLM for a box while rows are already pending, process pending rows according to the current config when the worker claims them; first v1 behavior should move them to review with an explicit config-disabled/never-evaluated decision path rather than silently accepting them.
- Treat this as intentionally operationally flexible rather than enqueue-time deterministic.

#### 3.2 Prompt Construction

- Build prompt construction as a pure, testable function before wiring any HTTP calls.
- Prompt layers:
  - system base policy: site-wide privacy, doxxing, identity speculation, harassment, threats, spam, explicit sexual content, fan drama, other;
  - output contract: explicitly require **json** output and include an example JSON object;
  - per owner/question-type additive policy text;
  - user content wrapped in delimiters, e.g. `<<<QUESTION>>> ... <<<END_QUESTION>>>`.
- Use project/domain terms in the prompt: submission, asker, owner console, question type, review queue, moderation category.
- Do not send to the model:
  - client IP, IP location, owner/admin token data, matched keyword text, full keyword list, or asker JWT/submission UUID unless a later design explicitly needs it.
- Keep prompt versioned, e.g. `aqbox-moderation-v1`, and store prompt version in events.
- Include a small prompt fixture/test suite with representative safe, doxxing, identity speculation, harassment, fan-drama, and spam examples.

#### 3.3 Formatted Output Contract

- Use DeepSeek/OpenAI-compatible JSON mode with `response_format: {"type": "json_object"}` when provider supports it.
- Because DeepSeek JSON mode requires the prompt to include the word `json`, include that word in the system/output instructions and include an example JSON object.
- Set `max_tokens` high enough for the full object so `finish_reason = "length"` does not truncate JSON under normal conditions.
- Validate parsed output with a strict internal schema:
  - `decision`: `accept | reject`
  - `moderation_category`: fixed site-tuned enum
  - `confidence`: float `0.0..1.0`
  - `short_reason`: short safe owner-list reason; must not quote original question content
  - `rationale`: detailed owner-facing explanation
- Normalize or reject invalid outputs:
  - empty content: provider error event and retry if attempts remain;
  - free text or Markdown/code-fenced JSON: invalid-response event and retry if attempts remain;
  - invalid JSON: provider error event and retry if attempts remain;
  - schema mismatch, extra fields, unknown enum, NaN, infinite confidence, or over-length strings: invalid-response event and retry if attempts remain;
  - any `finish_reason` other than `stop`, including `length`: invalid-response/provider event and retry if attempts remain;
  - `finish_reason = "content_filter"` or `insufficient_system_resource`: provider event and retry/fail according to attempts.
- Do not trust model-provided reason text without length limits and display-safe escaping through normal Vue rendering.

#### 3.4 Provider Interface And DeepSeek Adapter

- Define a provider interface independent of DeepSeek naming:
  - input: prompt/messages, model, timeout, response format flag, max tokens;
  - output: parsed raw response envelope including content, finish reason, model, latency, token usage, provider error class.
- Implement provider calls with `httpx.AsyncClient`; do not introduce the OpenAI SDK for this slice.
- Classify provider errors as:
  - `config_auth`: missing key, bad key, model/base URL configuration failures;
  - `rate_limited`: provider 429;
  - `timeout`: request timeout;
  - `network`: DNS/connectivity/TLS failures;
  - `server`: provider 5xx;
  - `invalid_response`: malformed, truncated, empty, or schema-invalid responses;
  - `quota_exceeded`: local circuit/cost cap exhaustion if added in this slice.
- Implement the DeepSeek adapter first:
  - endpoint: `POST /chat/completions`;
  - base URL default: `https://api.deepseek.com`;
  - models default to `deepseek-v4-flash`, allow config override to `deepseek-v4-pro`;
  - auth: `Authorization: Bearer ...`;
  - `temperature` low and `stream: false`;
  - disable provider retries in the HTTP client; retries belong to the DB-backed worker.
- Keep HTTP timeout below the worker lock/attempt cadence.
- Unit-test provider parsing with canned DeepSeek-style responses for stop, length, content_filter, empty content, 429/5xx, and invalid JSON.

#### 3.5 Worker And State Machine

- Add a moderation worker alongside the visit worker in FastAPI lifespan.
- Worker loop:
  - select due `pending` rows by `next_attempt_at`, `locked_until`, and attempt count;
  - acquire a short DB-backed lock before calling provider;
  - release/advance lock after success/failure;
  - on shutdown, stop accepting new work and let in-flight provider calls finish or time out.
- Never hold `Database.lock` or a SQLite write transaction across provider I/O.
- Use a lock owner token when claiming rows; only the matching owner can finalize, retry, or release the row.
- State transitions:
  - LLM queued: create `pending` state/event during submit after keyword pass and LLM policy match through atomic `insert_pending_question(...)`.
  - Accept: delete pending state row and append accepted event.
  - High-confidence reject: update to `blocked/source=llm` and append event.
  - Low-confidence reject: update to `blocked/source=llm_low_confidence/reason=needs_review` and append event.
  - Attempts exhausted/provider failure: update to `blocked/source=llm_error/reason=never_evaluated` and append event.
- With `review_all_model_rejects: true`, every model `reject` enters the review queue; `high_confidence_reject_threshold` only chooses source/reason framing.
- Preserve keyword-first behavior: keyword block skips LLM entirely.
- Prevent pending rows from appearing in normal/review/live/detail until resolved.
- Add `/ops/health` moderation worker details when LLM is enabled: enabled/running, pending/due/locked counts, last successful check, and recent error class. Redact secrets and raw prompt/question text.

#### 3.6 Persistence And Raw Retention

- Add a named migration `0005_llm_moderation_worker_fields` for worker metadata and parsed LLM display fields; keep `0004_moderation_state_events` as the keyword/review-table migration.
- Store parsed decision fields on `question_moderation_event`.
- Store current review display fields on `question_moderation_state`.
- Field semantics:
  - `reason`: stable machine code such as `keyword`, `needs_review`, `never_evaluated`;
  - `category`/`moderation_category`: stable site enum from the model output;
  - `short_reason`: compact owner-list text that does not quote the submission;
  - `rationale`: owner-detail explanation, length-limited and escaped by normal rendering;
  - `confidence`, `provider`, `model`, `prompt_version`, `policy_hash`, `config_hash`, `finish_reason`, token/latency metadata: stored for audit/debugging.
- Raw prompt/request/response:
  - default off;
  - when enabled, store on event with `purge_after`;
  - replace `purge_due_raw_audit_fields()` with `purge_due_raw_moderation_event_fields()` for event raw fields;
  - never log raw question text at INFO.
- Consider whether accepted events should keep `rationale`; default can store parsed decision metadata without owner-visible rationale because accepted rows have no state row.

#### 3.7 Real DeepSeek API Test Path

- Add a deliberately opt-in integration test or tool that calls the real DeepSeek API only when both `AQBOX_RUN_DEEPSEEK_INTEGRATION=1` and `DEEPSEEK_API_KEY` are present.
- Suggested command shape:
  - `AQBOX_RUN_DEEPSEEK_INTEGRATION=1 DEEPSEEK_API_KEY=... uv run pytest backend/tests/test_deepseek_integration.py -q`
  - or a backend tool `uv run python backend/tools/check_deepseek_moderation.py --text "..."`
- Integration test should verify:
  - auth/base URL/model config reaches DeepSeek;
  - JSON mode returns parseable content for safe and unsafe fixtures;
  - `short_reason` does not quote original text;
  - latency and finish reason are recorded;
  - no database write occurs unless the test is explicitly an end-to-end worker test against a temp DB.
- Keep this test skipped by default in CI and local smoke.
- Use `pytest.skip` when either opt-in variable is absent; do not print raw prompt text, raw response text, or the API key.
- Document expected costs/rate-limit behavior in the test/tool help text.

#### 3.8 End-To-End Local Validation

- Add backend tests with fake provider for deterministic worker behavior.
- Add an end-to-end temp-DB test that:
  - submits LLM-enabled safe text and waits for worker accept;
  - submits LLM-enabled reject text and waits for review queue entry;
  - forces provider failures and verifies `llm_error/never_evaluated`.
- Run owner smoke after Slice 3 with LLM disabled to prove existing flows still work.
- Optionally run a manual local preview with a real DeepSeek key and a non-production config before enabling any production config.

## LLM Output And Privacy

- Model returns both:
  - `short_reason`: safe badge/list reason that does not quote original content.
  - `rationale`: detailed owner-facing explanation.
- Store parsed short reason, detailed rationale, category, confidence, provider/model metadata.
- Raw prompt/request/response storage is config-only, defaults off, and when enabled lives in `question_moderation_event` with `purge_after` / `purged_at`.
- Update/replace the existing raw-audit purge helper to purge event raw fields.
- Asker routes expose no moderation metadata.

## Documentation Work

- Update `CONTEXT.md` glossary:
  - replace **Soft-delete** with **Owner deletion**;
  - add **Moderation block**;
  - add **Review queue**;
  - add **Owner approval**.
- Update `AGENTS.md` hard invariant language from keyword soft-delete to moderation block after Slice 2 changes land.
- Update `docs/contract/go-api-behavior.md` with a superseded-by-redesign note rather than silently rewriting legacy history.
- Update the deferred DeepSeek spec to point to this redesign and explicitly supersede sync/fail-open behavior.
- Add an ADR for dedicated moderation state/event tables, likely `docs/adr/0004-moderation-state-and-events.md`.
- Add ADR coverage for async LLM fail-to-review if it is not included in the same moderation ADR.

## Test Plan

- Update backend tests that currently lock old keyword `deleted_at` behavior:
  - keyword hit no longer sets `deleted_at`;
  - normal owner list hides moderation-blocked rows;
  - review queue/table can list and open them;
  - asker can still read them;
  - approve/delete work.
- Add migration tests for `0004_moderation_state_events` and idempotent bootstrap.
- Add repository/service tests for atomic keyword question + moderation state/event insertion.
- Keep owner/manual delete tests:
  - deleted rows remain inaccessible to normal list, review queue, detail, and live view;
  - owner-deleted rows remain asker-readable under current legacy behavior.
- Add tests for visibility matrix:
  - normal, pending, blocked, approved, owner-deleted.
- Add tests for `moderation_status`:
  - missing defaults to normal;
  - invalid value returns legacy-shaped 400;
  - normal/live views exclude blocked/pending;
  - review queue excludes pending and deleted.
- Add tests for `moderation_counts` and location options respecting moderation status.
- Add tests for approval idempotency and invalid approval states.
- Add test: answer blocked row, row remains absent from normal/live and present in review queue.
- Add async LLM tests in Slice 3 for pending/accept/block/low-confidence/error states.
- Frontend: smoke after Slice 1; then review table reveal/open/approve/delete flows.
