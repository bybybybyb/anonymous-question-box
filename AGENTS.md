# Agent Guide

## Project Shape

- `frontend/` is the Vue/Vite web app.
- `backend/` is the canonical FastAPI/Pydantic backend.
- `legacy/go_backend/` is the deprecated Go backend, retained only for historical reference.
- `backend/config/` and `test/*.db` are local-only runtime/preview artifacts and must not be committed.

## Backend Module Map

- `backend/aqbox/app.py` assembles the FastAPI app and lifespan.
- `backend/aqbox/routers.py` adapts HTTP routes to the legacy API contract.
- `backend/aqbox/services.py` owns behavior for submissions, owner console, visits, geo, auth, and ops.
- `backend/aqbox/repositories.py` is the service-facing SQLite boundary.
- `backend/aqbox/db.py` owns SQLite schema bootstrap, migrations, and SQL.
- `backend/aqbox/schemas.py` contains Pydantic request models.
- `backend/aqbox/legacy.py` preserves legacy error envelopes and manual request parsing.
- `backend/aqbox/settings_provider.py` handles hot reload, last-good config, and restart-required fields.
- `backend/aqbox/geo.py` handles trusted proxy IP resolution and offline ip2region lookup.

## Hard Invariants

- Preserve legacy `{"error": "..."}` envelopes on legacy routes.
- Do not let FastAPI's default 422 response leak from legacy routes.
- Keep JWTs wire-compatible with the Go-era frontend: HS256, `uuid`, `exp`, `iat`, `jwt_secret_key`, and admin `magic_spell`.
- Images remain unsupported until explicitly changed: profiles report `support_image: false`, reads return `images: []`, and non-empty submit `images` returns `400`.
- Asker routes must never expose `ip`, `ip_addr`, or `ip_isp`.
- Owner/admin routes may expose `ip`, `ip_addr`, and `ip_isp`.
- IP lookup uses configured offline ip2region xdb files; do not add runtime IP API calls or commit xdb files.
- Trust forwarded IP headers only when the direct peer is in `trusted_proxy_cidrs`.
- Keyword moderation is stealth soft-delete: submitter gets success; owner normal lists hide the submission.
- Do not add new features to `legacy/go_backend/`.

## Commands

```bash
uv sync --dev
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend/aqbox
uv run pytest -q
```

```bash
cd frontend
npm run lint -- --max-warnings=0
npm run build
npm run e2e:smoke
```

## Local Preview

```bash
AQBOX_CONFIG=backend/config/config.local.yaml uv run uvicorn aqbox.main:app --app-dir backend --host 127.0.0.1 --port 3768
```

```bash
cd frontend
./node_modules/.bin/vite --host 127.0.0.1 --port 5173
```

With the backend and frontend running, use the owner smoke flow:

```bash
cd frontend
AQBOX_E2E_CONFIG=../backend/config/config.local.yaml npm run e2e:smoke
```

When local geo is enabled and xdb paths are configured, include the optional geo assertions:

```bash
cd frontend
AQBOX_E2E_CONFIG=../backend/config/config.prod.local.yaml \
AQBOX_E2E_GEO_IP=223.5.5.5 \
AQBOX_E2E_GEO_ADDR=浙江省杭州市 \
AQBOX_E2E_GEO_ISP=阿里 \
npm run e2e:smoke
```
