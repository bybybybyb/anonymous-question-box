import assert from "node:assert/strict";
import test from "node:test";

import {
  activeQuestionTypes,
  applyBodyTheme,
  clearBodyTheme,
  ownerButtonLabel,
  ownerTheme,
  questionTypeEntries,
  siteMetadata,
  themeClass,
  themeVariant,
} from "../src/siteConfig.mjs";

function fakeBody(initialClasses = []) {
  const classes = new Set(initialClasses);
  return {
    classList: {
      add(...names) {
        names.forEach((name) => classes.add(name));
      },
      remove(...names) {
        names.forEach((name) => classes.delete(name));
      },
      contains(name) {
        return classes.has(name);
      },
      [Symbol.iterator]() {
        return classes[Symbol.iterator]();
      },
    },
    style: {
      background: "",
      backgroundColor: "",
      backgroundImage: "",
      backgroundPosition: "",
      backgroundRepeat: "",
      backgroundSize: "",
    },
    removeAttribute(name) {
      if (name === "style") {
        Object.keys(this.style).forEach((key) => {
          this.style[key] = "";
        });
      }
    },
  };
}

test("site metadata uses configured branding with stable fallbacks", () => {
  assert.deepEqual(
    siteMetadata({
      site: {
        title: "Portable Box",
        logo_url: "/assets/custom/logo.svg",
      },
    }),
    {
      title: "Portable Box",
      header_title: "Portable Box",
      hero_title: "Portable Box",
      logo_url: "/assets/custom/logo.svg",
      header_logo_url: "/assets/custom/logo.svg",
      hero_image_url: "/assets/custom/logo.svg",
      favicon_url: "",
    }
  );
});

test("site metadata falls back to neutral defaults when site config is absent", () => {
  assert.deepEqual(siteMetadata({}), {
    title: "Anonymous Question Box",
    header_title: "Anonymous Question Box",
    hero_title: "Anonymous Question Box",
    logo_url: "",
    header_logo_url: "",
    hero_image_url: "",
    favicon_url: "",
  });
});

test("site metadata rejects off-origin and CSS-breaking branding URLs", () => {
  const site = siteMetadata({
    site: {
      title: "Box",
      logo_url: "//evil.example.com/logo.svg",
      header_logo_url: 'http://x/a.png") , url("http://evil.example.com/track.png',
      favicon_url: "assets/custom/favicon.png",
      hero_image_url: "javascript:alert(1)",
    },
  });

  assert.equal(site.title, "Box");
  assert.equal(site.logo_url, "");
  assert.equal(site.header_logo_url, "");
  assert.equal(site.hero_image_url, "");
  assert.equal(site.favicon_url, "");
});

test("site metadata accepts the documented URL prefixes", () => {
  const site = siteMetadata({
    site: {
      logo_url: "/assets/custom/logo.svg",
      header_logo_url: "./logo.svg",
      hero_image_url: "../hero.svg",
      favicon_url: "https://cdn.example.com/favicon.png",
    },
  });

  assert.equal(site.logo_url, "/assets/custom/logo.svg");
  assert.equal(site.header_logo_url, "./logo.svg");
  assert.equal(site.hero_image_url, "../hero.svg");
  assert.equal(site.favicon_url, "https://cdn.example.com/favicon.png");
});

test("an invalid explicit logo falls back to a valid logo_url", () => {
  const originalWarn = console.warn;
  console.warn = () => {};
  let site;
  try {
    site = siteMetadata({
      site: {
        logo_url: "/assets/custom/logo.svg",
        header_logo_url: "javascript:alert(1)",
        hero_image_url: "//evil.example.com/hero.png",
      },
    });
  } finally {
    console.warn = originalWarn;
  }

  // Rejecting the explicit value must not discard the valid fallback with it.
  assert.equal(site.header_logo_url, "/assets/custom/logo.svg");
  assert.equal(site.hero_image_url, "/assets/custom/logo.svg");
});

test("unsafe background_image values are never applied to the body", () => {
  const body = fakeBody([]);
  globalThis.document = { body };

  applyBodyTheme({ background_image: "//evil.example.com/track.png" });

  assert.equal(body.style.backgroundImage, "");
});

test("owner button label prefers deployment copy", () => {
  assert.equal(
    ownerButtonLabel(
      {
        name: "owner",
        display_name: "Owner Name",
        button_label: "Ask Me",
      },
      "owner"
    ),
    "Ask Me"
  );
});

test("active question types do not assume the normal key", () => {
  const owner = {
    question_types: {
      closed: {
        description: "Closed",
        start_time: "2026-07-01T00:00:00Z",
        end_time: "2026-07-02T00:00:00Z",
      },
      snail: {
        description: "Snail mail",
        start_time: "2026-06-01T00:00:00Z",
        end_time: "2026-06-30T00:00:00Z",
      },
    },
  };

  assert.equal(
    activeQuestionTypes(owner, new Date("2026-06-22T00:00:00Z"))[0].name,
    "snail"
  );
});

test("theme class supports generic presets", () => {
  assert.equal(
    themeClass({ preset: "striped-dark" }),
    "body-theme-preset-striped-dark"
  );
});

test("theme class ignores preset names outside the generic set and warns", () => {
  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (message) => warnings.push(message);
  try {
    assert.equal(themeClass({ background_class: "striped-merry" }), "");
    assert.equal(themeClass({ background_class: "striped-merry" }), "");
    assert.equal(themeClass({ preset: "texture-umy-dark" }), "");
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(warnings.length, 2, "one warning per distinct rejected token");
  assert.match(warnings[0], /striped-merry/);
  assert.match(warnings[1], /texture-umy-dark/);
});

test("theme class rejects arbitrary class injection", () => {
  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (message) => warnings.push(message);
  try {
    assert.equal(themeClass({ background_class: "position-fixed" }), "");
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /position-fixed/);
});

test("question type entries treat the map key as the identifier", () => {
  const entries = questionTypeEntries({
    question_types: {
      normal: { name: "renamed", description: "Normal" },
    },
  });

  assert.equal(entries[0].name, "normal");
  assert.equal(entries[0].questionType.name, "normal");
  assert.equal(entries[0].questionType.description, "Normal");
});

test("theme variant derives from the resolved preset class", () => {
  assert.equal(themeVariant({ preset: "plain-dark" }), "dark");
  assert.equal(themeVariant({ preset: "striped-dark" }), "dark");
  assert.equal(themeVariant({ preset: "striped-light" }), "light");
  assert.equal(themeVariant({}), "light");
});

test("theme variant prefers an explicit variant or mode over the preset", () => {
  assert.equal(themeVariant({ variant: "dark" }), "dark");
  assert.equal(themeVariant({ mode: "dark", preset: "plain-light" }), "dark");
  assert.equal(themeVariant({ variant: "light", preset: "plain-dark" }), "light");
});

test("owner theme falls back to the generic preset regardless of owner name", () => {
  assert.deepEqual(ownerTheme({ name: "owner-a" }), {
    preset: "striped-light",
  });
  assert.deepEqual(ownerTheme({ name: "owner-b" }), {
    preset: "striped-light",
  });
});

test("owner theme prefers explicit config and gives owners a generic fallback", () => {
  const configured = { preset: "plain-dark" };
  assert.equal(ownerTheme({ name: "owner-a", theme: configured }), configured);
  assert.deepEqual(ownerTheme({ name: "owner-b" }), {
    preset: "striped-light",
  });
});

test("generic preset class is applied and removed cleanly", () => {
  const body = fakeBody(["bg-light"]);
  globalThis.document = { body };

  const handle = applyBodyTheme({ preset: "striped-light" });

  assert.equal(body.classList.contains("body-theme-preset-striped-light"), true);
  assert.equal(body.classList.contains("bg-light"), false);

  clearBodyTheme(handle);

  assert.equal(body.classList.contains("body-theme-preset-striped-light"), false);
  assert.equal(body.classList.contains("bg-light"), true);
});

test("clearing a nested theme restores the previous managed class and styles", () => {
  const body = fakeBody(["body-theme-preset-plain-dark", "app-shell"]);
  body.style.backgroundColor = "rgb(1, 2, 3)";
  globalThis.document = { body };

  const handle = applyBodyTheme({
    preset: "striped-light",
    background_color: "rgb(4, 5, 6)",
    background_size: "40px 40px",
  });

  clearBodyTheme(handle);

  assert.equal(body.classList.contains("body-theme-preset-plain-dark"), true);
  assert.equal(body.classList.contains("body-theme-preset-striped-light"), false);
  assert.equal(body.classList.contains("app-shell"), true);
  assert.equal(body.classList.contains("bg-light"), false);
  assert.equal(body.style.backgroundColor, "rgb(1, 2, 3)");
  assert.equal(body.style.backgroundSize, "");
});
