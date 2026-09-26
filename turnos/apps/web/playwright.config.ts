import { defineConfig, devices } from "@playwright/test";

/**
 * E2E contra a stack real: PostgreSQL + API Java (porta 8080, COOKIE_SECURE=false,
 * BOOTSTRAP_ADMIN_EMAIL=admin@turnos.test) + este Next em modo produção.
 * A API tem de estar a correr; o Next é arrancado aqui.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    ...devices["iPhone 13"],
    browserName: "chromium",
    locale: "pt-PT",
    timezoneId: "Europe/Lisbon",
  },
  webServer: {
    command: "pnpm start",
    url: "http://localhost:3000/entrar",
    reuseExistingServer: true,
    env: { API_URL: process.env.API_URL ?? "http://localhost:8080" },
  },
});
