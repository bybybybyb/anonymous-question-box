# Offline ip2region for IP geolocation

**Status:** Accepted (replaces pconline WIP)

The Python backend uses offline **ip2region** xdb files for IP geolocation. The server operator provides xdb paths in config; the repository does not commit or download xdb data. This replaces the earlier pconline HTTP/GBK lookup, which was WIP-only and never carried production cache data.

The lookup is fail-open. Submissions still persist **Client IP** when geolocation is disabled, misconfigured, or lookup fails; owner/admin responses keep returning `ip_addr: ""` when no cached **IP location label** exists. Asker routes never expose IP or location fields.

Config uses separate xdb paths for IPv4 and IPv6. IPv4 lookup uses `ip2region_ipv4_xdb_path`; IPv6 is skipped unless `ip2region_ipv6_xdb_path` is configured. The default cache policy is `vectorIndex` to keep memory bounded at about 512 KiB per xdb file while still avoiding repeated vector-index reads. Shared vector-index searchers are cached and searched under a lock because they own file handles. Xdb paths and cache policy are restart-required settings.

The `ip_geo` table keeps `ip` as the cache key. Rows inserted by the current provider use `provider = "ip2region"` and store the raw ip2region string. `addr` is the location label and future location-filter key; `isp` is stored separately for owner-friendly display and is exposed as `ip_isp` only on owner/admin routes. Stale WIP cache rows from previous providers are deleted during migration because they have no production value.

Production submissions created before IP capture do not have `question.ip`, so they cannot be backfilled from the database alone. A future non-blocking ops session may reconstruct high-confidence IPs from nginx access logs by matching successful `POST /questions/submit` events to `question.asked_at` timestamps, then populate `question.ip` and `ip_geo` with offline ip2region. That job must be dry-run first and skip ambiguous timestamp matches; owner/live list refresh must only query cached DB fields and must not perform per-row live lookup.

**Rejected:** pconline runtime HTTP lookup, ip-api.com free tier, committing xdb files to the repository, provider-migration backfill for WIP cache data.
