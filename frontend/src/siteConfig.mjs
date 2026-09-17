const DEFAULT_SITE = {
  title: "MeUmy的棉花糖",
  header_title: "MeUmy的棉花糖",
  hero_title: "MeUmy的棉花糖",
};

const BODY_THEME_CLASS_PREFIX = "body-theme-preset-";
const BODY_THEME_PRESETS = new Set(["plain-light", "plain-dark", "striped-light", "striped-dark"]);
const LEGACY_BODY_THEME_CLASSES = new Map([
  ["striped-merry", "body-background-striped-merry"],
  ["striped-umy", "body-background-striped-umy"],
  ["texture-merry-dark", "body-background-texture-merry-dark"],
  ["texture-merry-light", "body-background-texture-merry-light"],
  ["texture-umy-dark", "body-background-texture-umy-dark"],
  ["texture-umy-light", "body-background-texture-umy-light"],
]);
const MANAGED_BODY_THEME_CLASSES = new Set([
  ...Array.from(BODY_THEME_PRESETS, (preset) => BODY_THEME_CLASS_PREFIX + preset),
  ...LEGACY_BODY_THEME_CLASSES.values(),
]);

function asObject(value) {
  return value && typeof value === "object" ? value : {};
}

function cleanUrl(value) {
  const url = String(value || "").trim();
  if (!url) return "";
  if (
    url.startsWith("/") ||
    url.startsWith("./") ||
    url.startsWith("../") ||
    url.startsWith("https://") ||
    url.startsWith("http://") ||
    url.startsWith("data:")
  ) {
    return url;
  }
  return "";
}

export function siteMetadata(metadata = {}, legacyAssets = {}) {
  const hasSiteConfig = metadata.site && typeof metadata.site === "object";
  const site = asObject(metadata.site);
  const legacyLogoUrl = hasSiteConfig
    ? ""
    : legacyAssets.logo_url || "/marshmallow@300.png";
  const legacyHeaderLogoUrl = hasSiteConfig
    ? ""
    : legacyAssets.header_logo_url || legacyLogoUrl;
  const legacyFaviconUrl = hasSiteConfig
    ? ""
    : legacyAssets.favicon_url || "/marshmallow@32.png";
  return {
    ...DEFAULT_SITE,
    ...site,
    title: site.title || DEFAULT_SITE.title,
    header_title: site.header_title || site.title || DEFAULT_SITE.header_title,
    hero_title: site.hero_title || site.title || DEFAULT_SITE.hero_title,
    logo_url: cleanUrl(site.logo_url || legacyLogoUrl),
    header_logo_url: cleanUrl(
      site.header_logo_url || site.logo_url || legacyHeaderLogoUrl
    ),
    hero_image_url: cleanUrl(site.hero_image_url || site.logo_url || legacyLogoUrl),
    favicon_url: cleanUrl(site.favicon_url || legacyFaviconUrl),
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
  if (owner.name === "merry") {
    return { background_class: "texture-merry-light" };
  }
  if (owner.name === "umy") {
    return { background_class: "texture-umy-light" };
  }
  return { preset: "striped-light" };
}

export function questionTypeEntries(owner = {}) {
  return Object.entries(asObject(owner.question_types)).map(([name, questionType]) => ({
    name,
    questionType: {
      ...questionType,
      name: questionType.name || name,
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
  return BODY_THEME_PRESETS.has(preset) ? preset : "";
}

export function themeClass(theme = {}) {
  const preset = themePreset(theme);
  if (preset) return BODY_THEME_CLASS_PREFIX + preset;
  const legacyClass = String(theme.background_class || "").trim();
  return LEGACY_BODY_THEME_CLASSES.get(legacyClass) || "";
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
  const backgroundImageUrl = cleanUrl(theme.background_image);
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
