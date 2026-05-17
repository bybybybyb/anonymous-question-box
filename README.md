# Anonymous Question Box

Anonymous Q&A site with a Vue/Vite frontend and a FastAPI/Pydantic backend.

## Current Layout

- `frontend/` - Vue/Vite web app.
- `backend/` - canonical Python backend.
- `legacy/go_backend/` - deprecated Go backend kept for historical reference only.
- `schema/` - original schema reference.
- `deploy/` - deployment snippets, including nginx proxy config.

Do not add new backend behavior to `legacy/go_backend/`. It is not maintained from this branch onward.

## Backend

```bash
uv sync --dev
AQBOX_CONFIG=backend/config/config.local.yaml uv run uvicorn aqbox.main:app --app-dir backend --host 127.0.0.1 --port 3768
```

Checks:

```bash
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend/aqbox
uv run pytest -q
```

## Frontend

```bash
cd frontend
npm install
./node_modules/.bin/vite --host 127.0.0.1 --port 5173
```

Checks:

```bash
npm run lint -- --max-warnings=0
npm run build
```

## Local Artifacts

`backend/config/` and `test/*.db` are local-only preview/runtime artifacts and must not be committed.
