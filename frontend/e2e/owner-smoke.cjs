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

function loadConfig() {
  try {
    return yaml.load(fs.readFileSync(configPath, "utf8")) || {};
  } catch (err) {
    throw new Error(`Could not read AQBOX_E2E_CONFIG at ${configPath}: ${err.message}`, { cause: err });
  }
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

async function submitViaApi(request, owner, type, text) {
  const tokenResp = await request.get(`${baseUrl}/api/new`);
  if (!tokenResp.ok()) throw new Error(`GET /api/new failed: ${tokenResp.status()}`);
  const token = (await tokenResp.json()).token;
  const submitResp = await request.post(`${baseUrl}/api/questions/submit`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { owner, type, text, images: [] },
  });
  if (!submitResp.ok()) {
    throw new Error(`POST /api/questions/submit failed: ${submitResp.status()} ${await submitResp.text()}`);
  }
  return token;
}

async function waitForOwnerList(page) {
  await page.waitForResponse(
    (resp) => resp.url().includes("/api/owner/questions") && resp.request().method() === "POST",
    { timeout: 10_000 }
  );
}

async function selectQuestionType(page, type) {
  const radio = page.locator(`#${type}_receiver_radio`);
  if ((await radio.count()) > 0) {
    await radio.check();
  }
}

async function main() {
  const config = loadConfig();
  const ownerToken = signAdminToken(config);
  const browser = await chromium.launch({ headless: !headed });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
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

    await page.goto(`${baseUrl}/#/question/${owner}/new`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${baseUrl}/#/question/${owner}/new`);
    await selectQuestionType(page, type);
    await page.locator("textarea").fill(unique);
    await page.getByRole("button", { name: "提交" }).click();
    await page.getByRole("button", { name: "确认提交" }).click();
    await page.getByText("感谢投稿！").waitFor({ timeout: 10_000 });
    const qrCount = await page.locator("canvas, svg").count();
    if (qrCount < 1) throw new Error("QR code was not rendered after submission");
    const askerUrl = page.url();
    if (!askerUrl.includes("token=")) throw new Error("Submission URL does not include asker token");

    await page.goto(`${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${baseUrl}/#/owner/${owner}/dashboard?token=${ownerToken}`);
    await page.getByText(unique).waitFor({ timeout: 10_000 });

    await Promise.all([waitForOwnerList(page), page.locator("#reply_status").selectOption("-1")]);
    await page.getByText(unique).waitFor({ timeout: 10_000 });
    await Promise.all([waitForOwnerList(page), page.locator("#reply_status").selectOption("0")]);
    await Promise.all([waitForOwnerList(page), page.locator("#day_limit").selectOption("30")]);
    await Promise.all([waitForOwnerList(page), page.locator("#order").first().selectOption("2")]);
    await Promise.all([waitForOwnerList(page), page.locator("select").nth(4).selectOption("10")]);
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

    await page.goto(askerUrl);
    await page.getByText(answer).waitFor({ timeout: 10_000 });

    const liveText = `live auto ${Date.now()}`;
    const liveToken = await submitViaApi(page.request, owner, type, liveText);
    await page.goto(`${baseUrl}/#/owner/${owner}/live?token=${ownerToken}`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${baseUrl}/#/owner/${owner}/live?token=${ownerToken}`);
    await page.getByText(liveText).waitFor({ timeout: 10_000 });
    await page.locator(".card.shadow-sm.my-2").filter({ hasText: liveText }).first().getByText("← 投屏").click();
    await page.locator("#textProjectArea").getByText(liveText).waitFor({ timeout: 10_000 });

    await page.goto(`${baseUrl}/#/question?token=${liveToken}`);
    await page.getByText("直播中回应").waitFor({ timeout: 10_000 });

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
          "asker sees answer",
          "live auto reply",
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
