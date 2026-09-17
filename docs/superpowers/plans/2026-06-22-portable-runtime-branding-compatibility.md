# Portable Runtime Branding Compatibility Implementation Plan

> **Superseded:** This plan is complete, and Task 3 ("Restore Built-In MeUmy
> Theme Compatibility") has been deliberately reversed. The six
> `.body-background-*` preset rules and the bundled MeUmy assets named in
> Task 3 were removed from the core bundle so the frontend stays generic, and
> `themeClass({ background_class: "striped-merry" })` is now expected to
> return `""`. Do NOT execute Task 3 or re-add those files. Current guidance
> lives in `docs/adr/0006-runtime-site-config-and-assets.md` and
> `aqbox-ops/config/meumy.example.yaml`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish runtime-configurable AQBox deployments while preserving existing MeUmy configuration, styling, and mark-without-list-reload behavior.

**Architecture:** Keep `/api/profiles` as the runtime source of truth and make `frontend/src/siteConfig.mjs` the compatibility boundary for generic structured Themes and legacy MeUmy Theme names. Keep MeUmy assets compiled as fallbacks while Docker may additionally mount deployment-specific files at `/assets/custom`.

**Tech Stack:** FastAPI/Python, Vue 3 Options API, Vite, Node test runner, Playwright, nginx, Docker Compose.

---

### Task 1: Reconcile Latest Main Without Regressing Mark Behavior

**Files:**
- Preserve: `frontend/src/components/OwnerView.vue`
- Preserve: `frontend/src/components/LiveView.vue`
- Preserve: `frontend/e2e/owner-smoke.cjs`

- [ ] **Step 1: Stash the complete portability worktree**

Run: `git stash push --include-untracked -m "portable runtime branding before main sync"`

- [ ] **Step 2: Fast-forward local main**

Run: `git pull --ff-only origin main`

Expected: local `main` points at the latest `origin/main`.

- [ ] **Step 3: Reapply the portability stash**

Run: `git stash apply stash@{0}`

Expected: conflicts are limited to files changed by both the mark fix and portability work.

- [ ] **Step 4: Resolve mark behavior in both views**

Keep the latest-main implementation:

```js
markQuestion(q) {
  const mark = !q.marked;
  return this.axios.put(url, { owner: q.owner, type: q.type, mark }, options)
    .then(() => {
      q.marked = mark;
      if (this.markedOnly && !mark) {
        this.rows = this.rows.filter((row) => row.uuid !== q.uuid);
        this.total_count = Math.max(0, this.total_count - 1);
      }
    });
}
```

Do not call `onQueryChange()` after a successful mark.

- [ ] **Step 5: Preserve the smoke regression**

Keep `markWithoutReloadingOwnerList()` and its calls for both Owner console and
Live view in `frontend/e2e/owner-smoke.cjs`.

- [ ] **Step 6: Verify no unresolved conflict markers**

Run: `rg -n '^(<<<<<<<|=======|>>>>>>>)' . --glob '!frontend/node_modules/**'`

Expected: no output.

### Task 2: Add Runtime Config Unit-Test Harness

**Files:**
- Create: `frontend/test/siteConfig.test.mjs`
- Modify: `frontend/package.json`

- [ ] **Step 1: Add the test command and failing compatibility tests**

Add:

```json
"test": "node --test test/*.test.mjs"
```

Tests must assert:

```js
assert.equal(themeClass({ background_class: "striped-merry" }), "body-background-striped-merry");
assert.equal(themeClass({ preset: "striped-dark" }), "body-theme-preset-striped-dark");
assert.equal(activeQuestionTypes(owner, now)[0].name, "snail");
assert.equal(ownerButtonLabel(owner, "owner"), "Ask Me");
```

- [ ] **Step 2: Run tests to verify RED**

Run: `cd frontend && npm test`

Expected: FAIL because `themeClass` and complete legacy mappings do not exist.

- [ ] **Step 3: Add minimal exported compatibility helpers**

Export `themeClass(theme)` from `siteConfig.mjs`. It returns generic preset
classes or allowlisted legacy classes and returns an empty string for unknown
values.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `cd frontend && npm test`

Expected: all tests pass.

### Task 3: Restore Built-In MeUmy Theme Compatibility

**Files:**
- Modify: `frontend/src/siteConfig.mjs`
- Modify: `frontend/src/index.css`
- Restore: `frontend/src/assets/marshmallow.svg`
- Restore: `frontend/src/assets/marshmallow_light.svg`
- Restore: `frontend/src/assets/merry_dark_blue.svg`
- Restore: `frontend/src/assets/merry_light_grey.svg`
- Restore: `frontend/src/assets/umy_dark_red.svg`
- Restore: `frontend/src/assets/umy_light_grey.svg`
- Restore: `frontend/public/marshmallow@16.png`
- Restore: `frontend/public/marshmallow@32.png`
- Restore: `frontend/public/marshmallow@96.png`
- Restore: `frontend/public/marshmallow@180.png`
- Restore: `frontend/public/marshmallow@196.png`
- Restore: `frontend/public/marshmallow@300.png`
- Restore: `frontend/public/marshmallow@512.png`

- [ ] **Step 1: Add failing DOM Theme tests**

Use a minimal fake `document.body` to prove:

```js
applyBodyTheme({ background_class: "striped-merry" });
assert.equal(body.classList.contains("body-background-striped-merry"), true);
clearBodyTheme(handle);
assert.equal(body.classList.contains("bg-light"), true);
```

Also prove structured inline values override only their corresponding
background properties and are restored by `clearBodyTheme`.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd frontend && npm test`

Expected: legacy class application or exact restoration fails.

- [ ] **Step 3: Implement allowlisted legacy class application**

`applyBodyTheme()` must remove previous managed generic and legacy classes,
apply `themeClass(theme)`, and retain its exact pre-Theme state in the returned
handle. `clearBodyTheme()` restores that state.

- [ ] **Step 4: Restore original MeUmy CSS and assets**

Restore the six original `.body-background-*` rules and all original assets.
Keep the four generic `.body-theme-preset-*` rules alongside them.

- [ ] **Step 5: Run unit tests**

Run: `cd frontend && npm test`

Expected: all tests pass.

### Task 4: Complete Data-Driven Owner and Live Views

**Files:**
- Modify: `frontend/src/components/OwnerView.vue`
- Modify: `frontend/src/components/LiveView.vue`

- [ ] **Step 1: Add helper tests for Owner Theme fallback**

Add `ownerTheme(owner)` tests proving an explicit Owner Theme is returned, that
owner names `merry`/`umy` with no explicit Theme fall back to their legacy
textures, and that any other owner falls back to `{ preset: "striped-light" }`.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd frontend && npm test`

Expected: FAIL because `ownerTheme` is not exported.

- [ ] **Step 3: Implement and consume `ownerTheme`**

Use the helper in both Owner console and Live view. Store the returned
`applyBodyTheme()` handle and clear it in `beforeUnmount()`.

- [ ] **Step 4: Preserve mark and Question type behavior**

Both views retain local mark mutation from Task 1 and normalize stale persisted
Question type values to the first configured type.

- [ ] **Step 5: Run unit tests, lint, and build**

Run:

```bash
cd frontend
npm test
npm run lint -- --max-warnings=0
npm run build
```

Expected: all commands exit zero.

### Task 5: Backend and Deployment Verification

**Files:**
- Verify: `backend/aqbox/config.py`
- Verify: `backend/tests/test_backend_contract.py`
- Verify: `docker-compose.yml`
- Verify: `Dockerfile`
- Verify: `frontend/Dockerfile`
- Verify: `aqbox-ops/`

- [ ] **Step 1: Run backend checks**

Run:

```bash
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend/aqbox
uv run pytest -q
```

Expected: all commands exit zero.

- [ ] **Step 2: Validate and build Compose**

Run:

```bash
docker compose config
docker compose build
```

Expected: both commands exit zero.

- [ ] **Step 3: Run owner smoke**

Start backend and frontend with the documented local preview commands, then run:

```bash
cd frontend
AQBOX_E2E_CONFIG=../backend/config/config.local.yaml npm run e2e:smoke
```

Expected: smoke passes, including no owner-list request after mark in Owner
console and Live view.

- [ ] **Step 4: Review final diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors, no runtime config/database artifacts, and only
the intended portability, compatibility, test, deployment, and documentation
changes.
