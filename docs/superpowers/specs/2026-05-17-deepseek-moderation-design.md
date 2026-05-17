# DeepSeek LLM Moderation Design

> **Status: Phase 3 only — deferred; pending re-brainstorm.**  
> Do not implement during Python rewrite Phases 1–2. LLM moderation is isolated from backend parity and IP geo work. Delivery phasing: see [`2026-05-17-phased-python-rewrite-design.md`](./2026-05-17-phased-python-rewrite-design.md). Revisit this spec with a dedicated brainstorm/grill session before Phase 3 implementation.

## Scope

Add optional content moderation for question submissions via DeepSeek Chat Completions API, integrated into the Python backend `FilterChain` after keyword filtering. The Python rewrite defines the `QuestionFilter` protocol and a no-op stub in Phases 1–2; this document applies only when Phase 3 starts.

**Compatibility anchor:** Today (Go) keyword matches set `deleted_at` on insert but still return HTTP 200; askers can read their submission; owner lists exclude soft-deleted rows. LLM moderation v1 preserves that **stealth** UX unless config opts into explicit rejection.

---

## 1. Position in submit flow

```
POST /questions/submit
  → validate owner/type/window/rune limit
  → FilterChain.evaluate(text, context)
       1. KeywordFilter (sync, no I/O) — reject → skip LLM
       2. LLMFilter (sync HTTP, timeout) — optional when enabled
  → insert question (deleted_at if reject)
  → 200 { uuid, asked_at }
  → BackgroundTasks: geo lookup (unchanged)
```

**Sync by default:** LLM runs in the submit request with a hard timeout (default 2.5s). No "pending moderation" state in v1.

---

## 2. DeepSeek API integration

| Setting | Value |
|---------|--------|
| Base URL | `https://api.deepseek.com` |
| Endpoint | `POST /chat/completions` |
| Auth | `Authorization: Bearer {DEEPSEEK_API_KEY}` (env or config) |
| Default model | `deepseek-v4-flash` |
| Optional strict model | `deepseek-v4-pro` (per-owner config later) |

**Request shape (OpenAI-compatible):**

```json
{
  "model": "deepseek-v4-flash",
  "messages": [
    { "role": "system", "content": "<policy + JSON output rules>" },
    { "role": "user", "content": "<<<QUESTION>>>\n{user_text}\n<<<END>>>" }
  ],
  "response_format": { "type": "json_object" },
  "temperature": 0.1,
  "max_tokens": 64,
  "stream": false
}
```

**Expected model JSON (validated server-side):**

```json
{
  "decision": "accept",
  "category": "other",
  "confidence": 0.92
}
```

| Field | Rule |
|-------|------|
| `decision` | `accept` \| `reject` |
| `category` | `harassment` \| `spam` \| `pii` \| `doxxing` \| `other` |
| `confidence` | 0.0–1.0 |

**Reject when:** `decision == "reject"` AND `confidence >= llm_filter.confidence_threshold` (default 0.7).

**Do not send** to the model: IP, keyword list, owner slug, or matched keyword text (reduces injection and privacy risk).

---

## 3. Failure modes

| Event | Behavior |
|-------|----------|
| Valid `reject` above threshold | **Fail-closed** — soft-delete, `moderation_source=llm`, reason `llm:{category}` |
| Keyword match | **Fail-closed** — soft-delete, `moderation_source=keyword`, skip LLM |
| Timeout, 5xx, 429, invalid JSON, schema mismatch | **Fail-open** — accept (no `deleted_at`) |
| `finish_reason=length` or truncated JSON | **Fail-open** — metric `moderation.llm.invalid_response` |
| `finish_reason=content_filter` | **Fail-open** in v1 — metric `moderation.llm.provider_filtered` |
| Daily cap / circuit breaker open | **Fail-open** — keywords only |

Log metrics: `moderation.llm.reject`, `moderation.llm.error`, `moderation.llm.timeout` (no request body at INFO).

---

## 4. Configuration

```yaml
llm_filter:
  enabled: false
  model: deepseek-v4-flash
  timeout_seconds: 2.5
  confidence_threshold: 0.7
  min_runes: 5
  sample_rate: 1.0
  daily_max_calls: 0          # 0 = unlimited
  circuit_breaker_failures: 10
  circuit_breaker_cooldown_seconds: 300
  fail_mode: open               # open | closed (closed: reject on API error)
  ux: stealth                   # stealth | explicit
  log_request_bodies: false

deepseek_api_key: ""            # prefer env DEEPSEEK_API_KEY
deepseek_system_prompt: |        # policy extension; hot-reload
  You moderate anonymous questions for a VTuber Q&A site...
```

Hot-reload via same `watchfiles` loop as main config. **Never** hot-reload API key in production without restart (optional).

---

## 5. Schema migration

```sql
ALTER TABLE question ADD COLUMN moderation_source TEXT;
ALTER TABLE question ADD COLUMN moderation_reason TEXT;
```

| Column | Values | Visibility |
|--------|--------|------------|
| `moderation_source` | `keyword`, `llm`, `manual`, NULL | Admin only |
| `moderation_reason` | Short code, max 128 chars, e.g. `keyword`, `llm:harassment` | Admin only |

Owner list default: `deleted_at IS NULL` (unchanged). New admin-only body flag `include_moderated: true` on `POST /owner/questions` returns moderated rows for review.

---

## 6. UX modes

### Stealth (default)

- HTTP 200 on submit even when rejected
- Asker `GET /questions/question` unchanged (sees full text)
- Owner list excludes soft-deleted rows
- Matches current `filtered_keywords` behavior

### Explicit (breaking, opt-in)

- HTTP 422 `{"error": "投稿未通过审核"}`
- Requires frontend change to show error
- No soft-delete row inserted on explicit reject (product choice)

---

## 7. Cost and rate control

1. Keyword filter always runs first; **never call DeepSeek** on keyword reject.
2. `min_runes`, `sample_rate`, `daily_max_calls` for operator tuning.
3. App semaphore: max 10 concurrent DeepSeek HTTP calls.
4. No retry on 429 — fail-open immediately.
5. Circuit breaker after N consecutive failures.

---

## 8. Prompt injection defenses

- Fixed JSON schema validation; ignore free-form assistant text.
- User content only inside `<<<QUESTION>>>` delimiters.
- System prompt defines policy + output schema.
- Confidence threshold reduces flaky rejects.
- Keywords remain deterministic backstop.

---

## 9. Privacy

- Question text stored locally; DeepSeek is a subprocessor.
- Do not log full model responses or request bodies by default.
- Do not include IP in LLM prompts.
- Admin sees short reason codes only.

---

## 10. Testing matrix

| Case | Expected |
|------|----------|
| Keyword hit | 200, deleted_at set, no DeepSeek HTTP call |
| LLM reject high confidence | 200 (stealth), deleted_at, moderation_source=llm |
| LLM accept | 200, visible to owner |
| Timeout | 200, visible to owner (fail-open) |
| Invalid JSON from model | 200, visible (fail-open) |
| `enabled: false` | No HTTP to DeepSeek |

---

## 11. Interface boundary (Python rewrite)

```python
class LLMFilter:
    async def check(self, text: str, context: FilterContext) -> FilterResult:
        if not config.llm_filter.enabled:
            return FilterResult(action="accept")
        # Phase 3 — implement per this spec after re-brainstorm
```

---

## 12. Deferred — revisit in Phase 3 brainstorm

- Stealth vs explicit 422 long-term
- Per-owner `fail_mode: closed`
- Backfill `moderation_source` for historical keyword-only soft-deletes
