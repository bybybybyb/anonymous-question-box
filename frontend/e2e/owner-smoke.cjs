const crypto = require("crypto");
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
  if (!keywords.length) return ["keyword moderation review skipped: no filtered_keywords"];

  const text = `keyword moderation smoke ${Date.now()} ${keywords[0]}`;
  const askerToken = await submitViaApi(page.request, owner, type, text);

  await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`, type);
  if ((await page.getByText(text).count()) > 0) {
    throw new Error("Keyword-moderated submission leaked into normal owner list");
  }

  await Promise.all([waitForOwnerList(page), page.getByRole("button", { name: /审核队列/ }).click()]);
  const reviewRow = page.locator("tr").filter({ hasText: text }).first();
  await reviewRow.waitFor({ timeout: 10_000 });
  await reviewRow.getByText("keyword / keyword").waitFor({ timeout: 10_000 });

  await reviewRow.getByRole("button", { name: "打开" }).click();
  await page.locator("#answerModal").getByText("审核队列").waitFor({ timeout: 10_000 });
  await page
    .locator("#answerModal h6")
    .filter({ hasText: "审核：审核队列" })
    .filter({ hasText: "keyword" })
    .waitFor({ timeout: 10_000 });
  await page.locator("#answerModal .btn-close").click();
  await page.locator("#answerModal").waitFor({ state: "hidden", timeout: 10_000 });

  await Promise.all([waitForOwnerList(page), reviewRow.getByRole("button", { name: "通过" }).click()]);
  await reviewRow.waitFor({ state: "detached", timeout: 10_000 });

  await Promise.all([waitForOwnerList(page), page.getByRole("button", { name: /全部投稿/ }).click()]);
  await page.locator(".card.shadow-lg.m-3").filter({ hasText: text }).first().waitFor({ timeout: 10_000 });

  await page.goto(`${baseUrl}/#/question?token=${askerToken}`);
  await page.getByText(text).waitFor({ timeout: 10_000 });

  return ["keyword moderation review queue", "moderation detail metadata", "moderation approve"];
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
  await submitViaApi(page.request, llmTarget.owner, llmTarget.type, text);
  await waitForModerationWorker(page);

  await gotoWithQuestionTypeStorage(page, `${baseUrl}/#/owner/${llmTarget.owner}/dashboard?token=${ownerToken}`, llmTarget.type);
  await Promise.all([waitForOwnerList(page), page.getByRole("button", { name: /审核队列/ }).click()]);
  const reviewRow = page.locator("tr").filter({ hasText: text.slice(0, 40) }).first();
  await reviewRow.waitFor({ timeout: 10_000 });
  await reviewRow.getByText(/llm|doxxing|harassment|unsafe|spam/).first().waitFor({ timeout: 10_000 });

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
    await Promise.all([waitForOwnerList(page), card.getByText("标记", { exact: true }).first().click()]);
    await Promise.all([waitForOwnerList(page), page.getByText("只显示已标记").click()]);
    await page.getByText(unique).waitFor({ timeout: 10_000 });
    await Promise.all([waitForOwnerList(page), page.getByText("显示全部").click()]);

    await page.locator(".card.shadow-lg.m-3").filter({ hasText: unique }).first().getByText("打开").click();
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
    await page.getByText(liveText).waitFor({ timeout: 10_000 });
    await page.locator(".card.shadow-sm.my-2").filter({ hasText: liveText }).first().getByText("← 投屏").click();
    await page.locator("#textProjectArea").getByText(liveText).waitFor({ timeout: 10_000 });

    await page.goto(`${baseUrl}/#/question?token=${liveToken}`);
    await page.getByText("直播中回应").waitFor({ timeout: 10_000 });

    const optionalChecks = [
      ...(await assertExpiredQuestionTypeVisibility(page, ownerToken)),
      ...(await assertKeywordModerationReview(page, config, owner, type, ownerToken)),
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
