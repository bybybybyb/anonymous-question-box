# Runtime Site Config Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Docker deployments configurable for site branding, owner buttons, question types, and theme assets without rebuilding the frontend image.

**Architecture:** Keep `/api/profiles` as the single public runtime config contract. Backend config preserves `metadata.site`, owner display fields, and theme fields; Vue reads those fields and falls back to the legacy Merry/Umy assets only when config omits custom values. nginx serves mounted static deployment assets from `/assets/custom`.

**Tech Stack:** FastAPI/Pydantic-style Python config loader, Vue 3 Options API, Vite, nginx, Docker Compose.

---

### Task 1: Backend Config Contract

**Files:**
- Modify: `backend/aqbox/config.py`
- Test: `backend/tests/test_backend_contract.py`

- [ ] **Step 1: Add a failing backend test**

Add a test proving arbitrary public site metadata survives config loading and `/profiles` serialization:

```python
def test_profiles_preserve_site_metadata(tmp_path: Path) -> None:
    payload = config_payload(tmp_path)
    payload["metadata"]["site"] = {
        "title": "Custom Box",
        "header_title": "Custom Header",
        "logo_url": "/assets/custom/logo.svg",
        "hero_image_url": "/assets/custom/hero.svg",
        "favicon_url": "/assets/custom/favicon.png",
    }
    client, _ = config_client(tmp_path, payload=payload)

    with client:
        resp = client.get("/profiles")

    assert resp.status_code == 200
    assert resp.json()["metadata"]["site"]["title"] == "Custom Box"
    assert resp.json()["metadata"]["site"]["logo_url"] == "/assets/custom/logo.svg"
```

- [ ] **Step 2: Run the focused failing test**

Run: `uv run pytest backend/tests/test_backend_contract.py::test_profiles_preserve_site_metadata -q`

Expected before implementation: fail because `metadata.site` is discarded.

- [ ] **Step 3: Preserve public metadata keys**

Update `load_settings()` so `metadata` keeps all mapping keys from YAML while normalizing the legacy keys `introductions`, `console_prints`, and `admin`.

- [ ] **Step 4: Re-run the focused test**

Run: `uv run pytest backend/tests/test_backend_contract.py::test_profiles_preserve_site_metadata -q`

Expected: pass.

### Task 2: Frontend Runtime Site Helpers

**Files:**
- Create: `frontend/src/siteConfig.mjs`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Create `siteConfig.mjs`**

Export helpers for `siteMetadata(metadata)`, `ownerEntries(ownerProfiles)`, `ownerDisplayName(owner)`, `questionTypeEntries(owner)`, `activeQuestionTypes(owner)`, `applyBodyTheme(theme)`, and `clearBodyTheme(handle)`.

- [ ] **Step 2: Wire document metadata**

In `main.js`, after `/api/profiles`, set `document.title` from `metadata.site.title` and update favicon links when `metadata.site.favicon_url` exists.

- [ ] **Step 3: Add generic theme CSS**

Add no-brand fallback classes for generic stripe/light/dark backgrounds and keep existing Merry/Umy classes for compatibility.

### Task 3: Data-Driven Public Frontend

**Files:**
- Modify: `frontend/src/components/Main.vue`
- Modify: `frontend/src/components/Header.vue`
- Modify: `frontend/src/components/QuestionNew.vue`
- Modify: `frontend/src/components/QuestionView.vue`
- Modify: `frontend/src/components/OwnerView.vue`
- Modify: `frontend/src/components/LiveView.vue`

- [ ] **Step 1: Make homepage data-driven**

Render all Owners from `ownerProfiles`, show configured `metadata.site.hero_title`, `metadata.site.hero_image_url`, and owner `display_name` / `button_label` fallbacks.

- [ ] **Step 2: Make header data-driven**

Render `metadata.site.header_title` and `metadata.site.header_logo_url` / `logo_url`, and hide the contact button when `metadata.admin.link` is absent.

- [ ] **Step 3: Remove `normal` assumptions**

In `QuestionNew.vue`, initialize `type` from the first active Question type and redirect home with an alert when an Owner has no active Question type.

- [ ] **Step 4: Apply config-driven themes**

Replace direct `body-background-*` class manipulation with `applyBodyTheme()` in submission, answer, and owner/live views. Prefer structured theme fields and `preset`; keep `background_class` only as a legacy alias for known built-in presets.

### Task 4: Docker Assets And Docs

**Files:**
- Modify: `docker-compose.yml`
- Create: `aqbox-ops/assets/.gitignore`
- Modify: `aqbox-ops/config/config.example.yaml`
- Modify: `README.md`
- Modify: `backend/README.md`

- [ ] **Step 1: Mount runtime assets**

Add `${AQBOX_STATIC_ASSETS_DIR:-./aqbox-ops/assets}:/usr/share/nginx/html/assets/custom:ro` to the frontend service.

- [ ] **Step 2: Document mounted asset URLs**

Explain that deploy assets are referenced as `/assets/custom/<filename>` from `metadata.site` and `theme` fields.

- [ ] **Step 3: Update example config**

Show `metadata.site` and one configurable theme using `background_color`, `background_image`, `background_size`, and `variant`.

### Task 5: Verification

**Files:**
- No source changes unless verification finds a bug.

- [ ] **Step 1: Backend focused test**

Run: `uv run pytest backend/tests/test_backend_contract.py::test_profiles_preserve_site_metadata -q`

Expected: pass.

- [ ] **Step 2: Frontend lint and build**

Run: `cd frontend && npm run lint -- --max-warnings=0`

Expected: pass.

Run: `cd frontend && npm run build`

Expected: pass.

- [ ] **Step 3: Docker config and build**

Run: `docker compose config`

Expected: pass.

Run: `docker compose build`

Expected: pass.

- [ ] **Step 4: Runtime smoke**

Run compose, check `/api/profiles` and `/`, then stop containers and remove the temporary test volume.

Expected: `/api/profiles` returns configured `metadata.site`, `/` returns `200 OK`, and nginx proxies API requests to backend.
