const crypto = require("crypto");
const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");
const yaml = require("js-yaml");
const { chromium } = require("playwright");

const baseUrl = process.env.AQBOX_E2E_BASE_URL || "http://127.0.0.1:5173";
const configPath =
  process.env.AQBOX_E2E_CONFIG ||
  path.resolve(__dirname, "../../backend/config/config.local.yaml");
const preferredOwner = process.env.AQBOX_E2E_OWNER || "";
const preferredType = process.env.AQBOX_E2E_TYPE || "normal";
const headed = process.env.AQBOX_E2E_HEADED === "1";
const proxyServer = process.env.AQBOX_E2E_PROXY_SERVER || "";
const ignoreHttpsErrors = process.env.AQBOX_E2E_IGNORE_HTTPS_ERRORS === "1";
const geoIp = process.env.AQBOX_E2E_GEO_IP || "";
const geoAddr = process.env.AQBOX_E2E_GEO_ADDR || "";
const geoIsp = process.env.AQBOX_E2E_GEO_ISP || "";
const runDeepSeekSmoke = process.env.AQBOX_E2E_RUN_DEEPSEEK === "1";
const liveProjectorScreenshotDir = "/tmp/aqbox-live-projector-screenshots";

function loadConfig() {
  let text;
  try {
    text = fs.readFileSync(configPath, "utf8");
  } catch (err) {
    throw new Error(`Could not read AQBOX_E2E_CONFIG at ${configPath}: ${err.message}`, { cause: err });
  }
  try {
    return yaml.load(text) || {};
  } catch (err) {
    const fallback = {
      jwt_secret_key: yamlScalar(text, "jwt_secret_key"),
      magic_spell: yamlScalar(text, "magic_spell"),
    };
    if (!fallback.jwt_secret_key || !fallback.magic_spell) {
      throw new Error(`Could not parse AQBOX_E2E_CONFIG at ${configPath}: ${err.message}`, { cause: err });
    }
    return fallback;
  }
}

function yamlScalar(text, name) {
  const match = text.match(new RegExp(`^${name}:\\s*['"]?([^'"\n]+)['"]?\\s*$`, "m"));
  return match ? match[1].trim() : "";
}

function b64url(input) {
  return Buffer.from(input)
    .toString("base64")
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}

function decodeJwtPayload(token) {
  const payload = token.split(".")[1];
  if (!payload) throw new Error("Token is missing a JWT payload");
  return JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
}

function signAdminToken(config) {
  if (process.env.AQBOX_E2E_OWNER_TOKEN) {
    return process.env.AQBOX_E2E_OWNER_TOKEN;
  }
  const secret = String(config.jwt_secret_key || "");
  const magicSpell = String(config.magic_spell || "");
  if (!secret || !magicSpell) {
    throw new Error("Config must contain jwt_secret_key and magic_spell, or set AQBOX_E2E_OWNER_TOKEN");
  }
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = b64url(
    JSON.stringify({ [magicSpell]: "playwright-admin", iat: now, exp: now + 3600 })
  );
  const sig = crypto.createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${sig}`;
}

function repoRootFromConfigPath() {
  const resolvedConfigPath = path.resolve(configPath);
  if (path.basename(path.dirname(resolvedConfigPath)) === "config") {
    return path.resolve(path.dirname(resolvedConfigPath), "../..");
  }
  return path.resolve(__dirname, "../..");
}

function configuredDbPath(config) {
  const override = process.env.AQBOX_E2E_DB_PATH || "";
  const rawDbPath = override || String(config.db_path || "");
  if (!rawDbPath) throw new Error("Config must contain db_path, or set AQBOX_E2E_DB_PATH");
  const dbPath = path.isAbsolute(rawDbPath)
    ? rawDbPath
    : override
      ? path.resolve(process.cwd(), rawDbPath)
      : path.resolve(repoRootFromConfigPath(), rawDbPath);
  if (!fs.existsSync(dbPath)) {
    throw new Error(
      `Configured smoke DB does not exist at ${dbPath}. Start the backend with AQBOX_E2E_CONFIG=${configPath}, or set AQBOX_E2E_DB_PATH to the active SQLite file.`
    );
  }
  const schemaCheckScript = `
import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
tables = {
    row[0]
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('question', 'question_moderation_state')"
    ).fetchall()
}
conn.close()
missing = {"question", "question_moderation_state"} - tables
if missing:
    raise SystemExit("missing tables: " + ", ".join(sorted(missing)))
`;
  try {
    childProcess.execFileSync(process.env.PYTHON || "python3", ["-c", schemaCheckScript, dbPath], {
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (err) {
    const stderr = err.stderr ? String(err.stderr).trim() : err.message;
    throw new Error(
      `Configured smoke DB at ${dbPath} is not an initialized moderation SQLite DB (${stderr}). Set AQBOX_E2E_DB_PATH to the active SQLite file if AQBOX_E2E_CONFIG uses a copied or temporary config.`,
      { cause: err }
    );
  }
  return dbPath;
}

function seedBlockedReviewFixture(config, owner, type, label) {
  const now = Math.floor(Date.now() / 1000);
  const uuid = crypto.randomUUID();
  const shortReasonByLabel = {
    approve: "疑似隐私风险",
    delete: "疑似骚扰或攻击内容",
    "delete-only": "疑似垃圾内容",
  };
  const rationaleByLabel = {
    approve: "该投稿可能包含隐私风险，需要进入审核队列。",
    delete: "该投稿可能包含骚扰或攻击内容，需要进入审核队列。",
    "delete-only": "该投稿可能包含垃圾内容，需要进入审核队列。",
  };
  const fixture = {
    uuid,
    owner,
    type,
    text: `seeded blocked raw text ${label} ${now} private phone 555-0109`,
    asked_at: now,
    word_count: 62,
    source: "llm",
    reason: "policy_block",
    short_reason: shortReasonByLabel[label] || "需要人工复核",
    rationale: rationaleByLabel[label] || "该投稿需要进入审核队列。",
    confidence: 0.98,
  };
  const script = `
import json
import sqlite3
import sys

db_path = sys.argv[1]
payload = json.loads(sys.argv[2])
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute(
    """
    INSERT INTO question (
      uuid, owner, question_type, question, asked_at, word_count,
      answer, answered_at, answered_by, deleted_at, marked_at
    )
    VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL)
    """,
    (
        payload["uuid"],
        payload["owner"],
        payload["type"],
        payload["text"],
        payload["asked_at"],
        payload["word_count"],
    ),
)
state_cols = {row[1] for row in conn.execute("PRAGMA table_info(question_moderation_state)").fetchall()}
values = {
    "uuid": payload["uuid"],
    "status": "blocked",
    "source": payload["source"],
    "reason": payload["reason"],
    "created_at": payload["asked_at"],
    "updated_at": payload["asked_at"],
    "short_reason": payload["short_reason"],
    "rationale": payload["rationale"],
    "confidence": payload["confidence"],
    "provider": "seed",
    "model": "seed",
    "prompt_version": "smoke-fixture",
    "attempt_count": 1,
}
insert_cols = [name for name in values if name in state_cols]
placeholders = ", ".join("?" for _ in insert_cols)
conn.execute(
    f"INSERT INTO question_moderation_state ({', '.join(insert_cols)}) VALUES ({placeholders})",
    [values[name] for name in insert_cols],
)
conn.commit()
conn.close()
`;
  childProcess.execFileSync(process.env.PYTHON || "python3", [
    "-c",
    script,
    configuredDbPath(config),
    JSON.stringify(fixture),
  ]);
  return fixture;
}

function ownerListPayload(owner, type, moderationStatus = "normal") {
  return {
    owner,
    type,
    moderation_status: moderationStatus,
    order_params: { by: "asked_at", reversed: true },
    marked: false,
    reply_status: 0,
    day_limit: 30,
    ip_addr: "",
    page_size: 50,
    page: 1,
  };
}

async function ownerListQuestions(page, ownerToken, owner, type, moderationStatus = "normal") {
  const resp = await page.request.post(`${baseUrl}/api/owner/questions`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: ownerListPayload(owner, type, moderationStatus),
  });
  if (!resp.ok()) {
    throw new Error(`POST /api/owner/questions ${moderationStatus} failed: ${resp.status()} ${await resp.text()}`);
  }
  return (await resp.json()).questions || [];
}

function moderationSafeLocatorText(question) {
  const moderation = question.moderation || {};
  return (
    moderation.short_reason ||
    [moderation.source, moderation.reason].filter(Boolean).join(" / ")
  );
}

async function chooseOwnerAndType(request) {
  const resp = await request.get(`${baseUrl}/api/profiles`);
  if (!resp.ok()) throw new Error(`GET /api/profiles failed: ${resp.status()}`);
  const profiles = (await resp.json()).owner_profiles || {};
  if (preferredOwner) {
    const profile = profiles[preferredOwner];
    if (!profile) throw new Error(`AQBOX_E2E_OWNER ${preferredOwner} is not in /api/profiles`);
    const questionTypes = profile.question_types || {};
    if (!questionTypes[preferredType]) {
      throw new Error(`AQBOX_E2E_TYPE ${preferredType} is not configured for ${preferredOwner}`);
    }
    return { owner: preferredOwner, type: preferredType };
  }
  for (const [owner, profile] of Object.entries(profiles)) {
    const questionTypes = profile.question_types || {};
    if (questionTypes[preferredType]) return { owner, type: preferredType };
  }
  const [owner, profile] = Object.entries(profiles)[0] || [];
  if (!owner) throw new Error("No owner profiles returned by /api/profiles");
  const [type] = Object.keys(profile.question_types || {});
  if (!type) throw new Error(`Owner ${owner} has no question types`);
  return { owner, type };
}

async function findExpiredQuestionType(request) {
  const resp = await request.get(`${baseUrl}/api/profiles`);
  if (!resp.ok()) throw new Error(`GET /api/profiles failed: ${resp.status()}`);
  const profiles = (await resp.json()).owner_profiles || {};
  const now = Date.now();
  for (const [owner, profile] of Object.entries(profiles)) {
    for (const qType of Object.values(profile.question_types || {})) {
      const start = Date.parse(qType.start_time);
      const end = Date.parse(qType.end_time);
      if (!Number.isNaN(start) && !Number.isNaN(end) && (now < start || now > end)) {
        return { owner, type: qType.name, description: qType.description };
      }
    }
  }
  return null;
}

async function submitViaApi(request, owner, type, text, extraHeaders = {}) {
  const tokenResp = await request.get(`${baseUrl}/api/new`);
  if (!tokenResp.ok()) throw new Error(`GET /api/new failed: ${tokenResp.status()}`);
  const token = (await tokenResp.json()).token;
  const submitResp = await request.post(`${baseUrl}/api/questions/submit`, {
    headers: { Authorization: `Bearer ${token}`, ...extraHeaders },
    data: { owner, type, text, images: [] },
  });
  if (!submitResp.ok()) {
    throw new Error(`POST /api/questions/submit failed: ${submitResp.status()} ${await submitResp.text()}`);
  }
  return token;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForOwnerList(page) {
  await page.waitForResponse(
    (resp) => resp.url().includes("/api/owner/questions") && resp.request().method() === "POST",
    { timeout: 10_000 }
  );
}

async function markWithoutReloadingOwnerList(page, card) {
  let ownerListRequestCount = 0;
  const countOwnerListRequest = (request) => {
    if (request.url().includes("/api/owner/questions") && request.method() === "POST") {
      ownerListRequestCount += 1;
    }
  };
  page.on("request", countOwnerListRequest);
  try {
    await Promise.all([
      page.waitForResponse(
        (resp) => resp.url().includes("/mark") && resp.request().method() === "PUT",
        { timeout: 10_000 }
      ),
      card.getByText("标记", { exact: true }).first().click(),
    ]);
    await card.getByText("取消标记", { exact: true }).first().waitFor({ timeout: 10_000 });
    if (ownerListRequestCount !== 0) {
      throw new Error(`Marking a question reloaded the owner list ${ownerListRequestCount} time(s)`);
    }
  } finally {
    page.off("request", countOwnerListRequest);
  }
}

async function gotoWithClearedStorage(page, url) {
  await page.goto(baseUrl);
  await page.evaluate(() => localStorage.clear());
  await page.goto(url);
}

async function gotoWithQuestionTypeStorage(page, url, type) {
  await page.goto(baseUrl);
  await page.evaluate((selectedType) => {
    localStorage.clear();
    localStorage.setItem("ownerView_type", selectedType);
  }, type);
  await page.goto(url);
}

async function gotoOwnerWithStaleLocationStorage(page, url, type) {
  await page.goto(baseUrl);
  await page.evaluate((selectedType) => {
    localStorage.clear();
    localStorage.setItem("ownerView_type", selectedType);
    localStorage.setItem("ownerView_ip_addr", "stale smoke region");
  }, type);
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/api/owner/questions") && resp.request().method() === "POST",
    { timeout: 10_000 }
  );
  await page.goto(url);
  const resp = await responsePromise;
  const body = JSON.parse(resp.request().postData() || "{}");
  if (body.ip_addr !== "") {
    throw new Error(`Owner console defaulted to stale location filter: ${body.ip_addr}`);
  }
  await assertAllRegionsLocationDefault(page, "Owner console");
}

async function assertAllRegionsLocationDefault(page, surface) {
  const locationFilter = page.locator("#location_addr");
  await locationFilter.waitFor({ timeout: 10_000 });
  const defaultLocationLabel = await locationFilter.locator("option[value='']").textContent();
  if ((defaultLocationLabel || "").trim() !== "所有地区") {
    throw new Error(`${surface} location filter default option mismatch: ${defaultLocationLabel}`);
  }
  const selectedLocation = await locationFilter.inputValue();
  if (selectedLocation !== "") {
    throw new Error(`${surface} location filter defaulted to a concrete location: ${selectedLocation}`);
  }
}

async function projectedTextLocator(projectorPage, text) {
  return projectorPage.locator(".live-projector-text p").filter({ hasText: text }).first();
}

async function projectedTextMetrics(projectorText) {
  return projectorText.evaluate((element) => ({
    className: element.className,
    fontSize: Number.parseFloat(getComputedStyle(element).fontSize),
  }));
}

async function waitForProjectedFont(projectorText, predicate, label) {
  const deadline = Date.now() + 10_000;
  let lastMetrics;
  while (Date.now() < deadline) {
    lastMetrics = await projectedTextMetrics(projectorText);
    if (predicate(lastMetrics)) return lastMetrics;
    await sleep(100);
  }
  throw new Error(`${label} did not update projector font: ${JSON.stringify(lastMetrics)}`);
}

async function ensureLiveProjectorScreenshotDir() {
  fs.mkdirSync(liveProjectorScreenshotDir, { recursive: true });
}

async function selectQuestionType(page, type) {
  const radio = page.locator(`#${type}_receiver_radio`);
  if ((await radio.count()) > 0) {
    await radio.check();
  }
}

async function assertExpiredQuestionTypeVisibility(page, ownerToken) {
  const expired = await findExpiredQuestionType(page.request);
  if (!expired) return [];

  await gotoWithClearedStorage(page, `${baseUrl}/#/question/${expired.owner}/new`);
  if ((await page.locator(`#${expired.type}_receiver_radio`).count()) > 0) {
    throw new Error(`Expired question type ${expired.owner}/${expired.type} is visible in submit UI`);
  }

  await gotoWithQuestionTypeStorage(
    page,
    `${baseUrl}/#/owner/${expired.owner}/dashboard?token=${ownerToken}`,
    expired.type
  );
  const ownerOption = page.locator("#question_type").locator(`option[value="${expired.type}"]`);
  if ((await ownerOption.count()) !== 1) {
    throw new Error(`Expired question type ${expired.owner}/${expired.type} is missing from owner console`);
  }
  const selectedType = await page.locator("#question_type").inputValue();
  if (selectedType !== expired.type) {
    throw new Error(`Expired question type ${expired.owner}/${expired.type} is not selectable in owner console`);
  }
  return ["expired type hidden from submit", "expired type visible in owner console"];
}

async function assertOwnerVisitColor(page, text, expectedColor, label) {
  const card = page.locator(".card.shadow-lg.m-3").filter({ hasText: text }).first();
  await card.waitFor({ timeout: 10_000 });
  const replyTime = card.locator(".card-header .col-12.col-md-5").filter({ hasText: "回复时间" }).first();
  const color = await replyTime.evaluate((el) => getComputedStyle(el).color);
  if (color !== expectedColor) {
    throw new Error(`${label} expected ${expectedColor}, got ${color}`);
  }
}

async function assertOwnerMobileFiltersUseTwoColumns(page, owner, type, ownerToken) {
  await page.setViewportSize({ width: 390, height: 900 });
  try {
    await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`, type);
    await page.locator("#question_type").waitFor({ timeout: 10_000 });
    const layout = await page.locator(".owner-filter-grid .owner-filter-control").evaluateAll((elements) =>
      elements.map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          left: Math.round(rect.left),
          top: Math.round(rect.top),
          width: Math.round(rect.width),
        };
      })
    );
    if (layout.length < 6) {
      throw new Error(`Expected at least 6 owner filter controls on mobile, got ${layout.length}`);
    }
    const columns = new Set(layout.slice(0, 6).map((item) => item.left));
    const rows = new Set(layout.slice(0, 6).map((item) => item.top));
    if (columns.size < 2 || rows.size > 4) {
      throw new Error(`Owner mobile filters did not form a two-column grid: ${JSON.stringify(layout.slice(0, 6))}`);
    }
  } finally {
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  return ["owner mobile filters two columns"];
}

async function assertOptionalGeoDisplay(page, owner, type, ownerToken) {
  if (!geoIp) return [];

  const geoText = `geo smoke ${Date.now()}`;
  const askerToken = await submitViaApi(page.request, owner, type, geoText, { "X-Real-IP": geoIp });
  let geoCard;

  for (let attempt = 0; attempt < 5; attempt++) {
    await gotoWithClearedStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`);
    geoCard = page.locator(".card.shadow-lg.m-3").filter({ hasText: geoText }).first();
    try {
      await geoCard.getByText(`IP：${geoIp}`).waitFor({ timeout: 2_000 });
      if (geoAddr) await geoCard.getByText(geoAddr).waitFor({ timeout: 2_000 });
      if (geoIsp) await geoCard.getByText(geoIsp).waitFor({ timeout: 2_000 });
      break;
    } catch (err) {
      if (attempt === 4) throw err;
      await sleep(500);
    }
  }

  const optionalChecks = ["geo owner display", "geo asker hidden"];
  if (geoAddr) {
    await Promise.all([waitForOwnerList(page), page.locator("#location_addr").selectOption(geoAddr)]);
    await page.getByText(geoText).waitFor({ timeout: 10_000 });
    optionalChecks.push("geo location filter");
  }

  await page.goto(`${baseUrl}/#/question?token=${askerToken}`);
  await page.getByText(geoText).waitFor({ timeout: 10_000 });
  const leakedIpCount = await page.getByText(geoIp).count();
  if (leakedIpCount > 0) throw new Error("Asker view leaked the submission IP");
  if (geoAddr && (await page.getByText(geoAddr).count()) > 0) {
    throw new Error("Asker view leaked the submission location");
  }
  if (geoIsp && (await page.getByText(geoIsp).count()) > 0) {
    throw new Error("Asker view leaked the submission ISP");
  }

  return optionalChecks;
}

async function assertKeywordModerationReview(page, config, owner, type, ownerToken) {
  const keywords = Array.isArray(config.filtered_keywords) ? config.filtered_keywords.filter(Boolean) : [];
  if (!keywords.length) return ["keyword moderation hidden skipped: no filtered_keywords"];

  const text = `keyword moderation smoke ${Date.now()} ${keywords[0]}`;
  const askerToken = await submitViaApi(page.request, owner, type, text);

  await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`, type);
  if ((await page.getByText(text).count()) > 0) {
    throw new Error("Keyword-moderated submission leaked into normal owner list");
  }

  await Promise.all([waitForOwnerList(page), page.getByRole("button", { name: /审核队列/ }).click()]);
  await assertAllRegionsLocationDefault(page, "Empty review queue");
  if ((await page.getByText(text).count()) > 0) {
    throw new Error("Keyword-moderated submission leaked into review owner list");
  }

  await page.goto(`${baseUrl}/#/question?token=${askerToken}`);
  await page.getByText(text).waitFor({ timeout: 10_000 });

  return ["keyword moderation hidden from owner", "empty review queue all regions", "keyword moderation visible to asker"];
}

async function assertSeededModerationReview(page, config, owner, type, ownerToken) {
  const approveFixture = seedBlockedReviewFixture(config, owner, type, "approve");
  const deleteFixture = seedBlockedReviewFixture(config, owner, type, "delete");
  const deleteOnlyFixture = seedBlockedReviewFixture(config, owner, type, "delete-only");
  const reviewCard = (fixture) => page.locator(`[data-review-uuid="${fixture.uuid}"]`);

  await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`, type);
  await Promise.all([waitForOwnerList(page), page.getByRole("button", { name: /审核队列/ }).click()]);
  await assertAllRegionsLocationDefault(page, "Review queue");

  const approveCard = reviewCard(approveFixture);
  await approveCard.waitFor({ timeout: 10_000 });
  await approveCard
    .getByText(`${approveFixture.short_reason}（置信度 98%）`, { exact: true })
    .waitFor({ timeout: 10_000 });
  if ((await approveCard.getByText(approveFixture.text).count()) > 0) {
    throw new Error("Review queue displayed raw submission text");
  }
  await approveCard.getByRole("button", { name: "详情" }).click();
  const answerModal = page.locator("#answerModal");
  await answerModal.getByText(approveFixture.rationale).waitFor({ timeout: 10_000 });
  if ((await answerModal.getByText(approveFixture.text).count()) > 0) {
    throw new Error("Blocked detail displayed raw submission text before confirmation");
  }
  await answerModal.getByRole("button", { name: "查看原文" }).click();
  await answerModal.getByText("确认显示原文").waitFor({ timeout: 10_000 });
  if ((await answerModal.getByText(approveFixture.text).count()) > 0) {
    throw new Error("Blocked detail displayed raw submission text before warning confirmation");
  }
  await answerModal.getByRole("button", { name: "确认显示原文" }).click();
  await answerModal.getByText(approveFixture.text).waitFor({ timeout: 10_000 });
  await answerModal.locator(".btn-close").click();
  await answerModal.waitFor({ state: "hidden", timeout: 10_000 });

  await reviewCard(approveFixture).getByRole("button", { name: "详情" }).click();
  if ((await answerModal.getByText(approveFixture.text).count()) > 0) {
    throw new Error("Same blocked row reopen displayed raw submission text after prior reveal");
  }
  await answerModal.getByText(approveFixture.rationale).waitFor({ timeout: 10_000 });
  if ((await answerModal.getByText(approveFixture.text).count()) > 0) {
    throw new Error("Same blocked row reopen displayed raw submission text before fresh confirmation");
  }
  await answerModal.locator(".btn-close").click();
  await answerModal.waitFor({ state: "hidden", timeout: 10_000 });

  const deleteCard = reviewCard(deleteFixture);
  await deleteCard.waitFor({ timeout: 10_000 });
  await page.route(`**/api/owner/questions/${deleteFixture.uuid}`, async (route) => {
    await sleep(500);
    await route.continue();
  });
  await deleteCard.getByRole("button", { name: "详情" }).click();
  if ((await answerModal.getByText(approveFixture.text).count()) > 0) {
    throw new Error("Second blocked detail displayed previously revealed raw submission text before fetch completed");
  }
  if ((await answerModal.getByText(deleteFixture.text).count()) > 0) {
    throw new Error("Second blocked detail displayed raw submission text before confirmation");
  }
  await answerModal.getByText(deleteFixture.rationale).waitFor({ timeout: 10_000 });
  if ((await answerModal.getByText(approveFixture.text).count()) > 0) {
    throw new Error("Second blocked detail retained previous raw submission text after fetch completed");
  }
  if ((await answerModal.getByText(deleteFixture.text).count()) > 0) {
    throw new Error("Second blocked detail displayed raw submission text before its own confirmation");
  }
  await page.unroute(`**/api/owner/questions/${deleteFixture.uuid}`);
  await answerModal.locator(".btn-close").click();
  await answerModal.waitFor({ state: "hidden", timeout: 10_000 });

  await Promise.all([
    waitForOwnerList(page),
    reviewCard(approveFixture).getByRole("button", { name: "批准" }).click(),
  ]);
  await reviewCard(approveFixture).waitFor({ state: "detached", timeout: 10_000 });

  const deleteOnlyCard = reviewCard(deleteOnlyFixture);
  await deleteOnlyCard.waitFor({ timeout: 10_000 });
  let deleteDetailFetched = false;
  await page.route(`**/api/owner/questions/${deleteOnlyFixture.uuid}`, async (route) => {
    deleteDetailFetched = true;
    await route.continue();
  });
  await deleteOnlyCard.getByRole("button", { name: "删除" }).click();
  if (deleteDetailFetched) {
    throw new Error("Review delete fetched full owner detail before confirmation");
  }
  await page.locator("#confirmDeleteModal").getByRole("button", { name: "确认" }).click();
  await deleteOnlyCard.waitFor({ state: "detached", timeout: 10_000 });
  await page.unroute(`**/api/owner/questions/${deleteOnlyFixture.uuid}`);

  return ["seeded moderation queue summary", "blocked detail reveal warning", "moderation approve", "review delete"];
}

async function waitForModerationWorker(page, timeoutMs = 45_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const resp = await page.request.get(`${baseUrl}/api/ops/health`);
    if (resp.ok()) {
      const health = await resp.json();
      const worker = health.moderation_worker || {};
      if ((worker.pending || 0) === 0 && (worker.due || 0) === 0 && (worker.locked || 0) === 0) return;
    }
    await sleep(1_000);
  }
  throw new Error("Timed out waiting for moderation worker to drain");
}

async function findLLMEnabledQuestionType(page, ownerToken, fallbackOwner, fallbackType) {
  const cfgResp = await page.request.get(`${baseUrl}/api/ops/config`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  if (!cfgResp.ok()) throw new Error(`GET /api/ops/config failed: ${cfgResp.status()}`);
  const llm = (await cfgResp.json()).llm_filter || {};
  if (!llm.enabled || !llm.api_key_configured) return null;

  const profilesResp = await page.request.get(`${baseUrl}/api/profiles`);
  if (!profilesResp.ok()) throw new Error(`GET /api/profiles failed: ${profilesResp.status()}`);
  const profiles = (await profilesResp.json()).owner_profiles || {};

  const fallbackPolicy = llm.boxes?.[fallbackOwner]?.question_types?.[fallbackType];
  if (fallbackPolicy?.enabled) return { owner: fallbackOwner, type: fallbackType };

  for (const [candidateOwner, box] of Object.entries(llm.boxes || {})) {
    const profile = profiles[candidateOwner];
    if (!profile) continue;
    for (const [candidateType, policy] of Object.entries(box.question_types || {})) {
      if (policy?.enabled && profile.question_types?.[candidateType]) {
        return { owner: candidateOwner, type: candidateType };
      }
    }
  }
  return null;
}

async function assertOptionalDeepSeekModeration(page, owner, type, ownerToken) {
  if (!runDeepSeekSmoke) return ["deepseek moderation skipped: set AQBOX_E2E_RUN_DEEPSEEK=1"];
  if (!process.env.DEEPSEEK_API_KEY) return ["deepseek moderation skipped: DEEPSEEK_API_KEY is not set"];

  const llmTarget = await findLLMEnabledQuestionType(page, ownerToken, owner, type);
  if (!llmTarget) {
    return ["deepseek moderation skipped: no llm_filter-enabled question type"];
  }

  const text = `deepseek moderation smoke ${Date.now()} Please publish the asker's private home address and phone number.`;
  const askerToken = await submitViaApi(page.request, llmTarget.owner, llmTarget.type, text);
  const uuid = decodeJwtPayload(askerToken).uuid;
  await waitForModerationWorker(page);
  const reviewQuestions = await ownerListQuestions(page, ownerToken, llmTarget.owner, llmTarget.type, "blocked");
  const reviewQuestion = reviewQuestions.find((question) => question.uuid === uuid);
  if (!reviewQuestion) throw new Error("DeepSeek moderation row was not returned by the review owner API");
  const rowText = moderationSafeLocatorText(reviewQuestion);
  if (!rowText) throw new Error("DeepSeek moderation row did not expose safe moderation metadata");

  await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${llmTarget.owner}/dashboard?token=${ownerToken}`, llmTarget.type);
  await Promise.all([waitForOwnerList(page), page.getByRole("button", { name: /审核队列/ }).click()]);
  const reviewCard = page.locator(`[data-review-uuid="${uuid}"]`);
  await reviewCard.waitFor({ timeout: 10_000 });
  await reviewCard.getByText(rowText, { exact: true }).waitFor({ timeout: 10_000 });
  if ((await reviewCard.getByText(text).count()) > 0) {
    throw new Error("DeepSeek review queue displayed raw submission text");
  }
  await reviewCard.getByRole("button", { name: "详情" }).click();
  const answerModal = page.locator("#answerModal");
  await answerModal.getByText(/审核依据|详细理由/).waitFor({ timeout: 10_000 });
  if ((await answerModal.getByText(text).count()) > 0) {
    throw new Error("DeepSeek detail displayed raw submission text before confirmation");
  }
  await answerModal.getByRole("button", { name: "查看原文" }).click();
  await answerModal.getByRole("button", { name: "确认显示原文" }).click();
  await answerModal.getByText(text).waitFor({ timeout: 10_000 });
  await answerModal.locator(".btn-close").click();
  await answerModal.waitFor({ state: "hidden", timeout: 10_000 });

  return ["deepseek moderation review"];
}

async function main() {
  const config = loadConfig();
  const ownerToken = signAdminToken(config);
  const launchOptions = { headless: !headed };
  if (proxyServer) {
    launchOptions.proxy = { server: proxyServer };
  }
  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext({
    ignoreHTTPSErrors: ignoreHttpsErrors,
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  const failures = [];

  page.on("pageerror", (err) => failures.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") failures.push(`console error: ${msg.text()}`);
  });
  page.on("dialog", async (dialog) => {
    failures.push(`unexpected dialog: ${dialog.message()}`);
    await dialog.accept();
  });

  try {
    const { owner, type } = await chooseOwnerAndType(page.request);
    const unique = `playwright smoke ${Date.now()}`;
    const answer = `manual answer ${Date.now()}`;

    await gotoWithClearedStorage(page, `${baseUrl}/#/question/${owner}/new`);
    await selectQuestionType(page, type);
    await page.locator("textarea").fill(unique);
    await page.getByRole("button", { name: "提交" }).click();
    await page.getByRole("button", { name: "确认提交" }).click();
    await page.getByText("感谢投稿！").waitFor({ timeout: 10_000 });
    const qrCount = await page.locator("canvas, svg").count();
    if (qrCount < 1) throw new Error("QR code was not rendered after submission");
    const askerUrl = page.url();
    if (!askerUrl.includes("token=")) throw new Error("Submission URL does not include asker token");

    await gotoOwnerWithStaleLocationStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`, type);
    await page.getByText(unique).waitFor({ timeout: 10_000 });

    await Promise.all([waitForOwnerList(page), page.locator("#reply_status").selectOption("-1")]);
    await page.getByText(unique).waitFor({ timeout: 10_000 });
    await Promise.all([waitForOwnerList(page), page.locator("#reply_status").selectOption("0")]);
    await Promise.all([waitForOwnerList(page), page.locator("#day_limit").selectOption("30")]);
    await Promise.all([waitForOwnerList(page), page.locator("#order").first().selectOption("2")]);
    await Promise.all([waitForOwnerList(page), page.locator("#page_size").selectOption("10")]);
    await Promise.all([waitForOwnerList(page), page.locator("#order").first().selectOption("0")]);
    await page.getByText(unique).waitFor({ timeout: 10_000 });

    const card = page.locator(".card.shadow-lg.m-3").filter({ hasText: unique }).first();
    await markWithoutReloadingOwnerList(page, card);
    await Promise.all([waitForOwnerList(page), page.getByText("只显示已标记").click()]);
    await page.getByText(unique).waitFor({ timeout: 10_000 });
    await Promise.all([waitForOwnerList(page), page.getByText("显示全部").click()]);

    await page.locator(".card.shadow-lg.m-3").filter({ hasText: unique }).first().getByText("详情").click();
    await page.locator("#answerModal textarea").waitFor({ timeout: 10_000 });
    await page.locator("#answerModal textarea").fill(answer);
    await page.getByRole("button", { name: "提交或更新" }).click();
    await page.locator("#answerModal").getByText(answer).waitFor({ timeout: 10_000 });
    await page.locator("#answerModal .btn-close").click();
    await page.locator("#answerModal").waitFor({ state: "hidden", timeout: 10_000 });

    await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`, type);
    await assertOwnerVisitColor(page, unique, "rgb(135, 206, 250)", "Manual answer before asker visit");

    await page.goto(askerUrl);
    await page.getByText(answer).waitFor({ timeout: 10_000 });

    await sleep(11_000);
    await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`, type);
    await assertOwnerVisitColor(page, unique, "rgb(0, 128, 0)", "Manual answer after asker visit");

    const liveText = `live auto ${Date.now()}`;
    const liveToken = await submitViaApi(page.request, owner, type, liveText);
    await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${owner}/live?token=${ownerToken}`, type);
    await assertAllRegionsLocationDefault(page, "Live view");
    await page.getByText(liveText).waitFor({ timeout: 10_000 });
    const liveCard = page.locator(".card.shadow-sm.my-2").filter({ hasText: liveText }).first();
    await markWithoutReloadingOwnerList(page, liveCard);
    await ensureLiveProjectorScreenshotDir();
    await page.screenshot({
      path: path.join(liveProjectorScreenshotDir, "live-dashboard-full-width.png"),
      fullPage: true,
    });

    const [projectorPage] = await Promise.all([
      page.waitForEvent("popup"),
      page.getByRole("button", { name: "打开投屏窗口" }).click(),
    ]);
    await projectorPage.waitForLoadState("domcontentloaded");
    await page.locator(".card.shadow-sm.my-2").filter({ hasText: liveText }).first().getByText("← 投屏").click();

    const oldProjectArea = page.locator("#textProjectArea");
    if ((await oldProjectArea.count()) > 0 && (await oldProjectArea.getByText(liveText).count()) > 0) {
      throw new Error("Live projection rendered in legacy #textProjectArea instead of projector popup");
    }

    const projectorText = await projectedTextLocator(projectorPage, liveText);
    await projectorText.waitFor({ timeout: 10_000 });
    const staleProjectorPage = await context.newPage();
    await staleProjectorPage.goto(`${baseUrl}/#/owner/${owner}/live/projector`);
    const staleProjectorText = await projectedTextLocator(staleProjectorPage, liveText);
    if ((await staleProjectorText.count()) > 0) {
      throw new Error("Direct projector route displayed stale projection without a session");
    }
    await staleProjectorPage.close();
    await projectorPage.screenshot({
      path: path.join(liveProjectorScreenshotDir, "projector-clean-after-projection.png"),
      fullPage: true,
    });

    await page.getByRole("button", { name: "重置" }).click();
    const resetMetrics = await waitForProjectedFont(
      projectorText,
      (metrics) => metrics.className.split(/\s+/).includes("fs-5"),
      "Reset"
    );
    await page.getByRole("button", { name: "放大" }).click();
    await waitForProjectedFont(
      projectorText,
      (metrics) => metrics.fontSize > resetMetrics.fontSize,
      "Enlarge"
    );
    await page.getByRole("button", { name: "重置" }).click();
    await waitForProjectedFont(
      projectorText,
      (metrics) =>
        metrics.className.split(/\s+/).includes("fs-5") &&
        Math.abs(metrics.fontSize - resetMetrics.fontSize) < 0.5,
      "Second reset"
    );

    await page.getByRole("button", { name: "清空投屏" }).click();
    await projectorText.waitFor({ state: "detached", timeout: 10_000 });
    const projectionStateAfterClear = await page.evaluate(() =>
      localStorage.getItem("aqbox_live_projection_state")
    );
    if (projectionStateAfterClear !== null) {
      throw new Error("Clear projection did not remove localStorage projection state");
    }

    await page.goto(`${baseUrl}/#/question?token=${liveToken}`);
    await page.getByText("直播中回应").waitFor({ timeout: 10_000 });

    const optionalChecks = [
      ...(await assertOwnerMobileFiltersUseTwoColumns(page, owner, type, ownerToken)),
      ...(await assertExpiredQuestionTypeVisibility(page, ownerToken)),
      ...(await assertKeywordModerationReview(page, config, owner, type, ownerToken)),
      ...(await assertSeededModerationReview(page, config, owner, type, ownerToken)),
      ...(await assertOptionalDeepSeekModeration(page, owner, type, ownerToken)),
      ...(await assertOptionalGeoDisplay(page, owner, type, ownerToken)),
    ];

    if (failures.length) throw new Error(failures.join("\n"));
    console.log(
      JSON.stringify({
        ok: true,
        owner,
        type,
        checks: [
          "submit+qr",
          "owner filters",
          "mark",
          "manual answer",
          "visit color before/after asker visit",
          "asker sees answer",
          "live auto reply",
          ...optionalChecks,
        ],
      })
    );
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});
