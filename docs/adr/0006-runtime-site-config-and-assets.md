# Runtime site config and assets

**Status:** Accepted

Deployment-specific public UI shape comes from the backend `/profiles` contract, not a separate frontend config file. Static branding and theme files are supplied as nginx-served deployment assets referenced by URL from config, so operators can change Owners, Question types, copy, logos, and theme backgrounds without rebuilding the frontend image while the backend remains the source of truth for valid submission boxes.

Operational examples and legacy Merry/Umy assets live under `aqbox-ops/` so the frontend bundle stays generic while deployment config, static assets, ip2region mounts, and nginx snippets are discoverable in one place.

**Rejected:** baking deployment branding into the frontend image and adding a second frontend-only runtime config.
