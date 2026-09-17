import assert from "node:assert/strict";
import test from "node:test";

import {
  activeQuestionTypes,
  applyBodyTheme,
  clearBodyTheme,
  ownerButtonLabel,
  ownerTheme,
  siteMetadata,
  themeClass,
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

test("theme class ignores preset names outside the generic set", () => {
  assert.equal(themeClass({ background_class: "striped-merry" }), "");
  assert.equal(themeClass({ preset: "texture-umy-dark" }), "");
});

test("theme class rejects arbitrary class injection", () => {
  assert.equal(themeClass({ background_class: "position-fixed" }), "");
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
