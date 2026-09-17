# Anonymous Question Box

Anonymous Q&A site with a Vue/Vite frontend and a FastAPI/Pydantic backend.

## Current Layout

- `frontend/` - Vue/Vite web app.
- `backend/` - canonical Python backend.
- `legacy/go_backend/` - deprecated Go backend kept for historical reference only.
- `schema/` - original schema reference.
- `aqbox-ops/` - deployment config examples, static asset bundles, ip2region mount point, and nginx snippets.

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

## Docker Deployment

The Docker setup runs two services:

- `backend` - FastAPI app on the internal compose network.
- `frontend` - nginx serving the built Vue app and proxying `/api/*` to the backend.

Start from the tracked generic example config, then edit secrets and owner profile settings:

```bash
mkdir -p backend/config
cp aqbox-ops/config/config.example.yaml backend/config/config.docker.yaml
$EDITOR backend/config/config.docker.yaml
```

Run the stack:

```bash
AQBOX_CONFIG_DIR=./backend/config AQBOX_CONFIG_NAME=config.docker.yaml docker compose up --build -d
```

Open `http://127.0.0.1:8080`. To use another host port:

```bash
AQBOX_HTTP_PORT=80 AQBOX_CONFIG_DIR=./backend/config AQBOX_CONFIG_NAME=config.docker.yaml docker compose up --build -d
```

Runtime data is stored in the named Docker volume `aqbox-data` because the example config sets `db_path: /data/aqbox.sqlite3`. Keep real config files under `backend/config/` or another ignored path so secrets are not committed.

Deployment-specific public assets are mounted from `aqbox-ops/assets/` into the frontend container at `/assets/custom/`. Put logos, hero images, favicons, and theme backgrounds there, then reference them from your copied config:

```yaml
metadata:
  site:
    title: My Question Box
    header_logo_url: /assets/custom/logo-light.svg
    hero_image_url: /assets/custom/hero.svg
    favicon_url: /assets/custom/favicon.png
owner_profiles:
  owner:
    display_name: Owner Name
    button_label: Ask Owner Name
    question_types:
      normal:
        theme:
          preset: striped-light
          background_image: /assets/custom/question-background.png
          background_color: "#f8f9fa"
          background_size: 480px 480px
          variant: light
```

Use `AQBOX_STATIC_ASSETS_DIR=/path/to/assets` if you keep assets somewhere other than `aqbox-ops/assets/`.

Theme switching uses structured config. Use `preset` for built-in generic presets (`plain-light`, `plain-dark`, `striped-light`, `striped-dark`) and use `background_image`, `background_color`, `background`, `background_position`, `background_repeat`, `background_size`, and `variant` for deployment-specific looks.

The legacy Merry/Umy bundle now lives together under `aqbox-ops/`: copy `aqbox-ops/config/meumy.example.yaml` for that deployment and keep its referenced assets in `aqbox-ops/assets/meumy/`.

Optional offline IP geolocation still uses local ip2region xdb files. Put them under `aqbox-ops/ip2region/`, keep them untracked, then set the xdb paths in your copied config:

```yaml
geo_enabled: true
ip2region_ipv4_xdb_path: /ip2region/ip2region_v4.xdb
ip2region_ipv6_xdb_path: /ip2region/ip2region_v6.xdb
```

## Local Artifacts

`backend/config/` and `test/*.db` are local-only preview/runtime artifacts and must not be committed.

See `aqbox-ops/RUNBOOK.md` for the container deployment runbook.

Config is mounted as a directory so atomic editor saves are visible to backend hot reload.
Set `AQBOX_CONFIG_DIR` to that directory and `AQBOX_CONFIG_NAME` to the filename inside it.
