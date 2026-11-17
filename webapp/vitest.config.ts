import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    // La primera lectura de los ~600 JSON de data/ tarda varios segundos.
    testTimeout: 60_000,
  },
});
