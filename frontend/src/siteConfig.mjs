const DEFAULT_SITE = {
  title: "Anonymous Question Box",
  header_title: "Anonymous Question Box",
  hero_title: "Anonymous Question Box",
};

const BODY_THEME_CLASS_PREFIX = "body-theme-preset-";
const BODY_THEME_PRESETS = new Set(["plain-light", "plain-dark", "striped-light", "striped-dark"]);
const MANAGED_BODY_THEME_CLASSES = new Set(
  Array.from(BODY_THEME_PRESETS, (preset) => BODY_THEME_CLASS_PREFIX + preset)
);

function asObject(value) {
  return value && typeof value === "object" ? value : {};
}

const warnedMessages = new Set();

function warnOnce(message) {
  if (warnedMessages.has(message)) return;
  warnedMessages.add(message);
  if (typeof console !== "undefined" && typeof console.warn === "function") {
    console.warn(`[siteConfig] ${message}`);
  }
}

const ALLOWED_URL_PREFIXES = ["/", "./", "../", "https://", "http://", "data:"];

// Characters that would break out of the `url("...")` CSS value these URLs are
// interpolated into (quotes, backslashes), plus control characters.
function hasUnsafeUrlChars(url) {
  for (const char of url) {
    const code = char.charCodeAt(0);
    if (char === '"' || char === "\\" || code < 0x20 || code === 0x7f) return true;
  }
  return false;
}

function cleanUrl(value, field = "url") {
  const url = String(value || "").trim();
  if (!url) return "";
  // Protocol-relative URLs (//host/path) start with "/" but resolve off-origin,
  // which defeats the point of deployment-served branding.
  if (url.startsWith("//")) {
    warnOnce(`${field} rejected: protocol-relative URLs are not allowed (${JSON.stringify(url)})`);
    return "";
  }
  if (!ALLOWED_URL_PREFIXES.some((prefix) => url.startsWith(prefix))) {
    warnOnce(
      `${field} rejected: expected one of ${ALLOWED_URL_PREFIXES.join(", ")} (${JSON.stringify(url)})`
    );
    return "";
  }
  if (hasUnsafeUrlChars(url)) {
    warnOnce(`${field} rejected: contains characters unsafe inside a CSS url() (${JSON.stringify(url)})`);
    return "";
  }
  return url;
}

export function siteMetadata(metadata = {}) {
  const site = asObject(metadata.site);
  return {
    ...DEFAULT_SITE,
    ...site,
    title: site.title || DEFAULT_SITE.title,
    header_title: site.header_title || site.title || DEFAULT_SITE.header_title,
    hero_title: site.hero_title || site.title || DEFAULT_SITE.hero_title,
    // Kept even though no component reads it directly: the spread above passes config
    // keys straight through, so this line is what replaces an operator-supplied
    // `logo_url` with a validated one. It also seeds the header/hero fallbacks below.
    logo_url: cleanUrl(site.logo_url, "metadata.site.logo_url"),
    header_logo_url: cleanUrl(site.header_logo_url || site.logo_url, "metadata.site.header_logo_url"),
    hero_image_url: cleanUrl(site.hero_image_url || site.logo_url, "metadata.site.hero_image_url"),
    favicon_url: cleanUrl(site.favicon_url, "metadata.site.favicon_url"),
  };
}

export function ownerEntries(ownerProfiles = {}) {
  return Object.entries(asObject(ownerProfiles)).map(([slug, owner]) => ({
    slug,
    owner,
  }));
}

export function ownerDisplayName(owner = {}, fallback = "") {
  return owner.display_name || owner.label || owner.name || fallback;
}

export function ownerButtonLabel(owner = {}, fallback = "") {
  return owner.button_label || owner.question_button_label || ownerDisplayName(owner, fallback);
}

export function ownerTheme(owner = {}) {
  if (owner.theme && typeof owner.theme === "object") return owner.theme;
  return { preset: "striped-light" };
}

export function questionTypeEntries(owner = {}) {
  return Object.entries(asObject(owner.question_types)).map(([name, questionType]) => ({
    name,
    questionType: {
      ...questionType,
      // The map key is the identifier used in routes and `question_types[key]`
      // lookups, so it wins over any configured `name`.
      name,
    },
  }));
}

export function activeQuestionTypes(owner = {}, now = new Date()) {
  return questionTypeEntries(owner)
    .map(({ questionType }) => questionType)
    .filter((questionType) => {
      const startTime = Date.parse(questionType.start_time);
      const endTime = Date.parse(questionType.end_time);
      return isNaN(startTime) || isNaN(endTime) || (startTime <= now && endTime >= now);
    });
}

export function themeVariant(theme = {}) {
  if (theme.variant === "dark" || theme.mode === "dark") return "dark";
  if (theme.variant === "light" || theme.mode === "light") return "light";
  // Derive from the class actually applied, not from the preset name alone: legacy
  // `background_class` values resolve through `themeClass`, and reading the raw
  // token would report "light" for a dark legacy theme (dark body, light cards).
  return themeClass(theme).includes("dark") ? "dark" : "light";
}

function themePreset(theme = {}) {
  const preset = String(theme.preset || theme.background_preset || theme.background_class || "").trim();
  if (!preset) return "";
  if (BODY_THEME_PRESETS.has(preset)) return preset;
  warnOnce(
    `theme token ${JSON.stringify(preset)} is not a supported preset, so no background is applied. ` +
      `Supported: ${Array.from(BODY_THEME_PRESETS).join(", ")}. Deployment-specific theme names must ` +
      `be migrated to structured theme fields (background, background_image, background_color, ` +
      `background_position, background_repeat, background_size); see ` +
      `docs/adr/0006-runtime-site-config-and-assets.md.`
  );
  return "";
}

export function themeClass(theme = {}) {
  const preset = themePreset(theme);
  return preset ? BODY_THEME_CLASS_PREFIX + preset : "";
}

export function applyBodyTheme(theme = {}) {
  const body = document.body;
  const className = themeClass(theme);
  const previousInline = {
    background: body.style.background,
    backgroundColor: body.style.backgroundColor,
    backgroundImage: body.style.backgroundImage,
    backgroundPosition: body.style.backgroundPosition,
    backgroundRepeat: body.style.backgroundRepeat,
    backgroundSize: body.style.backgroundSize,
  };
  const previousClasses = Array.from(body.classList).filter((name) =>
    MANAGED_BODY_THEME_CLASSES.has(name)
  );
  const hadBgLight = body.classList.contains("bg-light");

  body.classList.remove(
    "bg-light",
    ...Array.from(MANAGED_BODY_THEME_CLASSES)
  );
  if (className) body.classList.add(className);
  if (theme.background) body.style.background = theme.background;
  if (theme.background_color) body.style.backgroundColor = theme.background_color;
  const backgroundImageUrl = cleanUrl(theme.background_image, "theme.background_image");
  if (backgroundImageUrl) body.style.backgroundImage = `url("${backgroundImageUrl}")`;
  if (theme.background_position) body.style.backgroundPosition = theme.background_position;
  if (theme.background_repeat) body.style.backgroundRepeat = theme.background_repeat;
  if (theme.background_size) body.style.backgroundSize = theme.background_size;

  return { className, previousClasses, previousInline, hadBgLight };
}

export function clearBodyTheme(handle = null) {
  const body = document.body;
  body.classList.remove(...Array.from(MANAGED_BODY_THEME_CLASSES));
  if (handle?.previousInline) {
    body.style.background = handle.previousInline.background;
    body.style.backgroundColor = handle.previousInline.backgroundColor;
    body.style.backgroundImage = handle.previousInline.backgroundImage;
    body.style.backgroundPosition = handle.previousInline.backgroundPosition;
    body.style.backgroundRepeat = handle.previousInline.backgroundRepeat;
    body.style.backgroundSize = handle.previousInline.backgroundSize;
  } else {
    body.removeAttribute("style");
  }
  if (handle) {
    body.classList.add(...handle.previousClasses);
    if (handle.hadBgLight) body.classList.add("bg-light");
    else body.classList.remove("bg-light");
  } else {
    body.classList.add("bg-light");
  }
}

export function setDocumentSite(site) {
  document.title = site.title;
  if (!site.favicon_url) return;
  let icon = document.querySelector("link[rel='icon'][data-runtime-site-icon='true']");
  if (!icon) {
    icon = document.createElement("link");
    icon.rel = "icon";
    icon.dataset.runtimeSiteIcon = "true";
    document.head.appendChild(icon);
  }
  icon.href = site.favicon_url;
}
