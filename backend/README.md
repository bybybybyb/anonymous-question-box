# Backend

This is the canonical backend for Anonymous Question Box.

Stack: FastAPI, Pydantic v2, PyJWT, PyYAML, httpx, sqlite3.

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

## Notes

- Legacy routes preserve `{"error": "..."}` envelopes rather than FastAPI's default 422 body.
- Images are intentionally unsupported: profiles advertise `support_image: false`, reads return `images: []`, and new image submissions are rejected.
- Geolocation uses pconline only; do not add ip-api.
- Forwarded IP headers are trusted only when the socket peer is in `trusted_proxy_cidrs`.
- Asker routes must never expose `ip` or `ip_addr`; owner/admin routes may expose them.
- The nginx proxy snippet in `deploy/nginx/aqbox-python.conf` overwrites `X-Real-IP` and `X-Forwarded-For` for production.
