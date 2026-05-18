# Backend

This is the canonical backend for Anonymous Question Box.

Stack: FastAPI, Pydantic v2, PyJWT, PyYAML, py-ip2region, sqlite3.

The previous Go implementation lives in `legacy/go_backend/` and is deprecated. Treat it as historical contract/reference material only.

## Run

```bash
uv sync --dev
AQBOX_CONFIG=backend/config/config.local.yaml uv run uvicorn aqbox.main:app --app-dir backend --host 127.0.0.1 --port 3768
```

## Tests And Checks

```bash
uv run pytest -q
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend/aqbox
```

## Nginx Log Backfill

Historical submissions created before IP capture can be backfilled from nginx access logs. Always dry-run first:

```bash
uv run python backend/tools/backfill_nginx_ips.py \
  --db test/anonymous_qbox_prod.db \
  --log /path/to/nginx/logs \
  --config backend/config/config.prod.local.yaml \
  --require-followup-get
```

The tool only matches successful submit logs to a single nearby `question.asked_at` row. Ambiguous timestamp clusters are reported and skipped. Add `--apply` only after reviewing the dry-run report.

## Notes

- Legacy routes preserve `{"error": "..."}` envelopes rather than FastAPI's default 422 body.
- SQLite schema changes use the lightweight in-process migration runner in `aqbox.db`; applied versions are recorded in `schema_migrations`.
- Images are intentionally unsupported: profiles advertise `support_image: false`, reads return `images: []`, and new image submissions are rejected.
- Optional event timestamps use `NULL` in SQLite for absence/not-yet-happened. Keep legacy zero/epoch sentinels at API serialization boundaries rather than storing them in the database.
- Geolocation uses offline ip2region xdb files configured by path; do not commit xdb files.
- IPv4 lookup uses `ip2region_ipv4_xdb_path`; IPv6 lookup is skipped unless `ip2region_ipv6_xdb_path` is configured.
- Forwarded IP headers are trusted only when the socket peer is in `trusted_proxy_cidrs`.
- Asker routes must never expose `ip`, `ip_addr`, or `ip_isp`; owner/admin routes may expose them.
- The nginx proxy snippet in `deploy/nginx/aqbox-python.conf` overwrites `X-Real-IP` and `X-Forwarded-For` for production.
- Example geo config lives in `docs/config/geo-ip2region.example.yaml`.
- `ip2region_*_xdb_path` and `ip2region_cache_policy` are restart-required settings. Prefer versioned durable paths such as `/opt/aqbox/ip2region/2026-05/...` when rotating xdb files.

```yaml
geo_enabled: true
ip2region_ipv4_xdb_path: /opt/aqbox/ip2region/2026-05/ip2region_v4.xdb
ip2region_ipv6_xdb_path: /opt/aqbox/ip2region/2026-05/ip2region_v6.xdb
ip2region_cache_policy: vectorIndex
```
