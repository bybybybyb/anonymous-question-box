# Portable Runtime Branding Compatibility Design

> **Superseded:** The core frontend bundle is now branding-neutral. This
> document's "Compatibility Contract" — that legacy `theme.background_class`
> values (`striped-merry`, `striped-umy`, `texture-merry-dark`,
> `texture-merry-light`, `texture-umy-dark`, `texture-umy-light`) remain
> supported, and that MeUmy assets stay compiled into the frontend bundle as
> fallbacks — no longer holds. Those presets and bundled assets were removed
> from the core; unsupported theme tokens now apply no background and log a
> console warning. Deployment branding is supplied as configuration plus
> assets under `aqbox-ops/`. Do not re-add the removed aliases or assets to
> the frontend bundle. Current guidance lives in
> `docs/adr/0006-runtime-site-config-and-assets.md` and
> `aqbox-ops/config/meumy.example.yaml`.

## Goal

Make AQBox portable across deployments without requiring a frontend rebuild for
branding changes, while preserving existing MeUmy configuration, assets, theme
names, and visual behavior.

## Compatibility Contract

- `/api/profiles` remains the only public runtime configuration contract.
- Existing owner and question type maps continue to work without renaming
  `merry`, `umy`, or `normal`.
- Existing `theme.background_class` values remain supported:
  `striped-merry`, `striped-umy`, `texture-merry-dark`,
  `texture-merry-light`, `texture-umy-dark`, and `texture-umy-light`.
- Existing MeUmy assets remain compiled into the frontend as fallback assets.
- New deployments may use structured Theme fields and mounted
  `/assets/custom/*` URLs.
- Marking a Submission in Owner console or Live view updates the visible row
  locally and must not reload the owner list.

## Architecture

The backend preserves public Site metadata and Theme fields from YAML when it
serializes `/profiles`. `frontend/src/siteConfig.mjs` is the frontend
compatibility boundary: it normalizes Site metadata, Owners, Question types,
legacy Theme aliases, and structured Theme fields. Vue components consume that
normalized data instead of embedding deployment-specific names.

The generic Docker deployment mounts deployment assets at
`/assets/custom`. Built-in MeUmy files remain available from the frontend
bundle, so existing deployments do not depend on that mount.

## Theme Resolution

Structured Theme fields take precedence over a preset. Supported structured
fields are `background`, `background_color`, `background_image`,
`background_position`, `background_repeat`, `background_size`, and `variant`.

Generic presets are `plain-light`, `plain-dark`, `striped-light`, and
`striped-dark`. Legacy `background_class` values map to built-in CSS classes
with their original MeUmy styling. Unknown class names are ignored rather than
being placed directly on the DOM.

Applying a Theme records the previous body classes and inline background
properties. Clearing it restores those exact values, so nested route changes
do not leak or erase unrelated body styling.

## Frontend Behavior

- Site title, header title, hero title, logo, hero image, and favicon come from
  Site metadata. There are no bundled branding assets: an asset field that
  `metadata.site` omits resolves to `""`, and with no `metadata.site` at all every
  asset field resolves to `""` too. A partial `site:` block therefore renders no
  logo, hero image, or favicon. The neutral placeholder title and favicon live in
  `frontend/index.html`, not in the bundle.
- The homepage renders every configured Owner and uses display/button-label
  fallbacks.
- Submission pages choose the first currently active Question type rather than
  assuming `normal`.
- Owner console and Live view validate persisted Question type values against
  the current Owner.
- Owner console and Live view apply the configured Owner Theme.
- Mark actions mutate the row locally after the API succeeds. In marked-only
  mode, unmarking removes the row and decrements the displayed total.

## Testing

- Python contract tests verify Site metadata survives configuration loading.
- Node unit tests exercise Site, Owner, Question type, structured Theme, legacy
  Theme, and Theme restoration helpers.
- Existing Playwright smoke coverage verifies mark actions do not trigger owner
  list reloads in both Owner console and Live view.
- Full backend checks, frontend lint/build/unit tests, Compose validation/build,
  and the owner smoke flow are the completion gate.
