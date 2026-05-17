# pconline.com.cn for IP geolocation

**Status:** Accepted (amends earlier ip-api draft)

The Python rewrite (Phase 2) uses **pconline.com.cn** (`https://whois.pconline.com.cn/ipJson.jsp?ip={ip}&json=true`), not ip-api.com. Lookup runs after submit in a background task (Phase 2), decodes the GBK JSON response, caches rows in `ip_geo`, and stores a display string in `addr` (exposed as `ip_addr` in admin/owner API responses). Cache insert uses `INSERT OR IGNORE` per IP; existing rows are never bulk re-looked up or migrated from another provider. Private/reserved IPs are skipped; API failures are silent (no retry queue). **Fail-open:** `question.ip` is always persisted on submit; when lookup fails or is skipped, admin JSON includes `ip_addr: ""` (empty string), not omitted.

**Historical implementation reference:** `legacy/go_backend/internal/usecase/geoip.go` when present in old worktrees. Current implementation lives in `backend/aqbox/geo.py`.

**Rejected:** ip-api.com free tier, provider migration backfill.
