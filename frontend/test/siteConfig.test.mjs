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

test("site metadata preserves the legacy MeUmy title when site config is absent", () => {
  assert.deepEqual(siteMetadata({}), {
    title: "MeUmy的棉花糖",
    header_title: "MeUmy的棉花糖",
    hero_title: "MeUmy的棉花糖",
    logo_url: "/marshmallow@300.png",
    header_logo_url: "/marshmallow@300.png",
    hero_image_url: "/marshmallow@300.png",
    favicon_url: "/marshmallow@32.png",
  });
});

test("site metadata accepts bundled legacy asset URLs from the app entrypoint", () => {
  assert.deepEqual(
    siteMetadata(
      {},
      {
        logo_url: "/built/marshmallow.svg",
        header_logo_url: "/built/marshmallow-light.svg",
        favicon_url: "/built/marshmallow-32.png",
      }
    ),
    {
      title: "MeUmy的棉花糖",
      header_title: "MeUmy的棉花糖",
      hero_title: "MeUmy的棉花糖",
      logo_url: "/built/marshmallow.svg",
      header_logo_url: "/built/marshmallow-light.svg",
      hero_image_url: "/built/marshmallow.svg",
      favicon_url: "/built/marshmallow-32.png",
    }
  );
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

test("theme class preserves legacy MeUmy aliases", () => {
  assert.equal(
    themeClass({ background_class: "striped-merry" }),
    "body-background-striped-merry"
  );
});

test("theme class rejects arbitrary class injection", () => {
  assert.equal(themeClass({ background_class: "position-fixed" }), "");
});

test("owner theme preserves implicit legacy MeUmy textures", () => {
  assert.deepEqual(ownerTheme({ name: "merry" }), {
    background_class: "texture-merry-light",
  });
  assert.deepEqual(ownerTheme({ name: "umy" }), {
    background_class: "texture-umy-light",
  });
});

test("owner theme prefers explicit config and gives portable owners a generic fallback", () => {
  const configured = { preset: "plain-dark" };
  assert.equal(ownerTheme({ name: "merry", theme: configured }), configured);
  assert.deepEqual(ownerTheme({ name: "portable" }), {
    preset: "striped-light",
  });
});

test("legacy MeUmy theme class is applied and removed cleanly", () => {
  const body = fakeBody(["bg-light"]);
  globalThis.document = { body };

  const handle = applyBodyTheme({ background_class: "striped-merry" });

  assert.equal(body.classList.contains("body-background-striped-merry"), true);
  assert.equal(body.classList.contains("bg-light"), false);

  clearBodyTheme(handle);

  assert.equal(body.classList.contains("body-background-striped-merry"), false);
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
