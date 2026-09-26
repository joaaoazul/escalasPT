import next from "eslint-config-next";

const config = [
  ...next,
  { ignores: [".next/**", "node_modules/**", "src/lib/api/schema.d.ts", "playwright-report/**", "test-results/**"] },
];

export default config;
