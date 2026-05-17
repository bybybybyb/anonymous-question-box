# Python Backend

FastAPI/Pydantic rewrite of the Go backend.

## Run

```bash
uv sync --dev
AQBOX_CONFIG=./config/config.yaml uv run uvicorn aqbox.main:app --app-dir python_backend --host 0.0.0.0 --port 3768
```

## Tests

```bash
uv run pytest -q
uv run ruff check python_backend
uv run mypy python_backend/aqbox
```

## Notes

- Phase 1 intentionally disables image support and forces `/profiles` to report `support_image: false`.
- Phase 2 geolocation is enabled with `geo_enabled: true` and uses pconline only.
- Forwarded IP headers are trusted only when the socket peer is in `trusted_proxy_cidrs`.
- The nginx proxy snippet in `deploy/nginx/aqbox-python.conf` overwrites `X-Real-IP` and `X-Forwarded-For` for production.
