import js from "@eslint/js";
import vue from "eslint-plugin-vue";
import globals from "globals";

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  ...vue.configs["flat/essential"],
  {
    files: ["**/*.{js,vue}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
        Vue: "readonly",
      },
    },
    rules: {
      "no-empty": "off",
      "no-prototype-builtins": "off",
      "no-unused-vars": "warn",
      "vue/multi-word-component-names": "off",
      "vue/no-deprecated-data-object-declaration": "off",
      "vue/no-reserved-component-names": "off",
      "vue/no-shared-component-data": "off",
      "vue/no-unused-components": "off",
      "vue/require-valid-default-prop": "off",
    },
  },
];
