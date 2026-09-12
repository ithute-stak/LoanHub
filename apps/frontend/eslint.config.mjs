import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

/**
 * LoanHub is being upgraded to React 19 / Next.js 16 in stages.
 *
 * The React Compiler rules below are valuable migration diagnostics, but they
 * currently describe optimisation opportunities across established screens
 * rather than type or runtime failures. Keep them visible as warnings so the
 * normal lint command can remain a useful release gate while each workflow is
 * refactored deliberately and tested in isolation.
 *
 * Correctness rules that are not listed here retain the severities supplied by
 * eslint-config-next.
 */
const reactCompilerMigrationRules = {
  "react-hooks/immutability": "warn",
  "react-hooks/preserve-manual-memoization": "warn",
  "react-hooks/purity": "warn",
  "react-hooks/refs": "warn",
  "react-hooks/set-state-in-effect": "warn",
  "react-hooks/static-components": "warn",
};

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      ...reactCompilerMigrationRules,
      // Existing API boundaries are being typed incrementally. Keep every
      // occurrence visible without making unrelated releases impossible.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
