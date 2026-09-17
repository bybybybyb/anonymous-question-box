# AQBox Ops Runbook

`aqbox-ops/` contains deployment-facing examples and static assets. Keep real
secrets and local runtime files in ignored paths such as `backend/config/`.

## Directory Layout

- `config/config.example.yaml` - generic Docker config example.
- `config/meumy.example.yaml` - legacy Merry/Umy config example.
- `assets/meumy/` - legacy Merry/Umy logos, favicons, and backgrounds.
- `assets/` - default static asset mount for custom deployment files.
- `ip2region/` - default ignored mount for local xdb files.
- `nginx/` - nginx snippets for container and Python deployments.

## Generic Docker Deployment

```bash
cp aqbox-ops/config/config.example.yaml backend/config/config.docker.yaml
$EDITOR backend/config/config.docker.yaml
AQBOX_CONFIG_FILE=./backend/config/config.docker.yaml docker compose up --build -d
```

The compose defaults point at `aqbox-ops/config/config.example.yaml`,
`aqbox-ops/assets`, and `aqbox-ops/ip2region`. Override them with
`AQBOX_CONFIG_FILE`, `AQBOX_STATIC_ASSETS_DIR`, and `AQBOX_IP2REGION_DIR`.

## Legacy MeUmy Deployment

```bash
cp aqbox-ops/config/meumy.example.yaml backend/config/config.docker.yaml
$EDITOR backend/config/config.docker.yaml
AQBOX_CONFIG_FILE=./backend/config/config.docker.yaml docker compose up --build -d
```

The MeUmy config references host-mounted files under `/assets/custom/meumy/...`
(they are not baked into any image). Those URLs resolve because Docker mounts
`aqbox-ops/assets` into the frontend container at
`/usr/share/nginx/html/assets/custom`.

## Custom Branding

Put deployment-specific logos, favicons, hero images, and backgrounds under
`aqbox-ops/assets/`, or point `AQBOX_STATIC_ASSETS_DIR` at another directory.
Reference them from `metadata.site`, Owner `theme`, and Question type `theme`
fields as `/assets/custom/<filename>`.

The frontend reads `/api/profiles` at startup, so site title/logo/hero/favicon,
owners, question types, and theme backgrounds are backend config rather than
compiled frontend code.

Use `preset` only for built-in generic theme presets: `plain-light`,
`plain-dark`, `striped-light`, and `striped-dark`. Deployment-specific themes
should use structured fields such as `background_image`, `background_color`,
`background`, `background_position`, `background_repeat`, `background_size`,
and `variant`.

## Offline Geo

Put local ip2region xdb files under `aqbox-ops/ip2region/`, keep them untracked,
then configure paths inside the container:

```yaml
geo_enabled: true
ip2region_ipv4_xdb_path: /ip2region/ip2region_v4.xdb
ip2region_ipv6_xdb_path: /ip2region/ip2region_v6.xdb
ip2region_cache_policy: vectorIndex
```
