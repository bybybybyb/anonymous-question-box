# Legacy Go API Behavior Catalog

This catalog records the Phase 1 compatibility contract for the Python backend.
The Python implementation intentionally preserves the legacy frontend-facing API
except where noted as a documented non-parity change.

The Go implementation that originally defined this behavior now lives in
`legacy/go_backend/` and is deprecated. Current backend development happens in
`backend/`.

## Phase 1 MUST Behaviors

- `GET /checkalive` returns plain text `pong`.
- `GET /profiles` returns `owner_profiles` and `metadata`; Python Phase 1 forcibly emits every `question_type.support_image` as `false`.
- `GET /new` returns a Go-compatible HS256 JWT with `uuid`, `exp`, and `iat`.
- Protected routes return `403 {"error":"无效token"}` for missing/invalid Bearer shape.
- Bad JWT parse/validation returns `401 {"error":"无法解析token，错误信息：..."}`.
- Admin JWT detection uses the dynamic claim named by `magic_spell`.
- User JWT on owner routes returns `401 {"error":"未授权访问"}`.
- Admin JWT on submit returns `403 {"error":"提问箱主人能问自己和其他提问箱主人问题嘛？答案是不能"}`.
- `POST /questions/submit` trims `text`, rejects empty text with `400 {"error":"空投稿"}`, enforces owner/type rune limits, validates optional flight windows, and rejects unknown owner/type with the existing Chinese message.
- Keyword matches are stealth soft-deleted: insert with `deleted_at`, return `200 {uuid, asked_at}`, asker can read it, owner normal lists exclude it.
- Python Phase 1 rejects any non-empty `images` with `400 {"error":"本提问箱不支持图片上传"}` and never writes `image` rows.
- Python Phase 1 read/list/detail responses always include `images: []`; this is an intentional non-parity change from Go nil-slice JSON.
- Python Phase 1 never emits `ip`, `ip_addr`, or `ip_isp`.
- `GET /questions/question` returns DB `NULL answered_at` as Unix epoch RFC3339, not `null`.
- Non-admin `GET /questions/question` for an answered submission enqueues visit tracking.
- Owner list supports sort keys `asked_at` and `word_count`; invalid sort keys are rejected with a legacy-shaped 400 as a security hardening exception.
- Owner list excludes `deleted_at IS NOT NULL`.
- Owner answer, mark, and delete routes return empty `200` responses on success.

## Phase 2 Behaviors

- Add `question.ip` and `ip_geo` idempotently.
- Store client IP only after trusted-proxy validation.
- Lookup uses configured offline ip2region xdb files; no runtime IP API is called.
- Cache the human-readable location label in `ip_geo.addr`, store ISP separately, and expose `ip` / `ip_addr` / `ip_isp` only to owner/admin responses.
- Geo failures are fail-open: `ip` remains stored and `ip_addr` is `""`.

## Phase 3 Behaviors

- DeepSeek moderation is opt-in per owner/question type config.
- Missing policy disables LLM calls for that box.
- Keyword filtering runs before LLM and skips LLM on keyword soft-delete.
- Default UX is stealth soft-delete.
- Raw moderation audit lives in `question_moderation_audit` and is purged by retention while permanent decision metadata remains.
