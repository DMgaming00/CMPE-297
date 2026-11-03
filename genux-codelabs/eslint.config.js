import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/dist/**", "**/node_modules/**", "docs/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "@typescript-eslint/consistent-type-imports": "error",
      "no-restricted-syntax": [
        "error",
        { selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']", message: "Never inject model output as HTML; use <SandboxedHtml> or the component registry." },
      ],
    },
  },
);
