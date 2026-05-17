# Python Backend

FastAPI/Pydantic rewrite of the Go backend.

## Run

```bash
python3 -m venv /private/tmp/aqbox-venv
/private/tmp/aqbox-venv/bin/pip install -e '.[test]'
AQBOX_CONFIG=./config/config.yaml /private/tmp/aqbox-venv/bin/uvicorn aqbox.main:app --app-dir python_backend --host 0.0.0.0 --port 3768
```

## Tests

```bash
/private/tmp/aqbox-venv/bin/pytest -q
```

## Notes

- Phase 1 intentionally disables image support and forces `/profiles` to report `support_image: false`.
- Phase 2 geolocation is enabled with `geo_enabled: true` and uses pconline only.
- Forwarded IP headers are trusted only when the socket peer is in `trusted_proxy_cidrs`.
