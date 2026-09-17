import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import * as Vue from "vue";
import { parse } from "@vue/compiler-sfc";
import { compile } from "@vue/compiler-dom";

const { descriptor } = parse(
  readFileSync(new URL("../src/components/QuestionNew.vue", import.meta.url), "utf8")
);
const render = new Function("Vue", compile(descriptor.template.content, { prefixIdentifiers: true }).code)(Vue);

for (const { ownerProfiles, type = "", hasForm = false } of [
  { ownerProfiles: {} },
  { ownerProfiles: { owner: { question_types: {} } } },
  {
    ownerProfiles: {
      owner: {
        question_types: {
          normal: { description: "Closed", start_time: "2020-01-01", end_time: "2020-02-01" },
        },
      },
    },
  },
  {
    ownerProfiles: { owner: { question_types: { mail: { description: "Mail" } } } },
    type: "mail",
    hasForm: true,
  },
]) {
  test(`submission form renders safely: ${JSON.stringify({ ownerProfiles, type })}`, () => {
    const errors = [];
    const elements = [];
    const renderer = Vue.createRenderer({
      createElement: (tag) => {
        elements.push(tag);
        return { addEventListener() {}, removeEventListener() {} };
      },
      createText: () => ({}),
      createComment: () => ({}),
      insert() {},
      remove() {},
      setElementText() {},
      setText() {},
      parentNode: () => null,
      nextSibling: () => null,
      patchProp() {},
    });
    const app = renderer.createApp({
      render,
      data: () => ({ owner: "owner", type, ownerProfiles, questionTypes: [] }),
    });
    app.config.errorHandler = (error) => errors.push(error.message);
    app.config.warnHandler = () => {};
    app.mount({});
    assert.deepEqual(errors, []);
    assert.equal(elements.includes("textarea"), hasForm);
    app.unmount();
  });
}
