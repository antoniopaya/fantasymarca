// @ts-check
import eslintPluginAstro from "eslint-plugin-astro";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist/**", ".astro/**", "node_modules/**"],
  },
  // Reglas de eslint-plugin-astro para .astro (incluye accesibilidad vía jsx-a11y).
  ...eslintPluginAstro.configs["flat/jsx-a11y-recommended"],
  {
    // Solo .ts plano: los bloques de frontmatter/<script> de .astro ya los
    // cubre el parser propio de eslint-plugin-astro de arriba.
    files: ["**/*.ts"],
    extends: [...tseslint.configs.recommended],
  },
  {
    rules: {
      // define:vars mete variables del frontmatter en <script> como si vinieran
      // de fuera; no tiene sentido pedir que no se usen "sin declarar".
      "no-undef": "off",
    },
  },
);
