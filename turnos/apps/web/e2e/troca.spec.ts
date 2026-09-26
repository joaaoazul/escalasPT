import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const H = { "X-Requested-With": "turnos" };
const PASS = "palavra-passe-segura";
const run = Date.now().toString(36);

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const target = new Date(Date.now() + 10 * 864e5);
const DAY = iso(target);

async function post(req: APIRequestContext, path: string, data?: unknown) {
  const r = await req.post(path, { headers: H, data });
  expect(r.ok(), `${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? null : r.json();
}

async function register(req: APIRequestContext, email: string, fullName: string, rank: string) {
  return post(req, "/api/v1/auth/register", { email, password: PASS, fullName, rank });
}

async function typeId(req: APIRequestContext, postoId: string, code: string): Promise<string> {
  const types = await (await req.get(`/api/v1/postos/${postoId}/shift-types`)).json();
  return types.find((t: { code: string }) => t.code === code).id;
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/${name}.png` });
}

test("militar entra por convite, pinta a escala e troca com um camarada de outro grupo", async ({ page, browser, playwright }) => {
  // ── preparação pela API: administrador, posto, dois grupos e os comandantes de grupo ──
  const admin = await playwright.request.newContext({ baseURL: "http://localhost:3000" });
  await register(admin, `admin@turnos.test`, "Administrador", "").catch(async () => {
    await post(admin, "/api/v1/auth/login", { email: "admin@turnos.test", password: PASS });
  });
  const posto = await post(admin, "/api/v1/postos", { name: `Posto Territorial de Castro Marim ${run}`, location: "Castro Marim" });
  const g1 = await post(admin, `/api/v1/postos/${posto.id}/groups`, { name: "Grupo 1" });
  const g2 = await post(admin, `/api/v1/postos/${posto.id}/groups`, { name: "Grupo 2" });

  const cmd1 = await playwright.request.newContext({ baseURL: "http://localhost:3000" });
  await register(cmd1, `matos.${run}@gnr.test`, "Sofia Matos", "Cabo-Chefe");
  await post(cmd1, `/api/v1/invites/${(await post(admin, `/api/v1/groups/${g1.id}/invites`, { role: "COMMANDER" })).code}/accept`);
  const invite = await post(cmd1, `/api/v1/groups/${g1.id}/invites`, { email: `ana.${run}@gnr.test`, name: "Ana Silva", rank: "Guarda" });

  // Camarada do Grupo 2 com OC3 no dia da troca
  const rui = await playwright.request.newContext({ baseURL: "http://localhost:3000" });
  await register(rui, `rui.${run}@gnr.test`, "Rui Rocha", "Cabo");
  await post(rui, `/api/v1/invites/${(await post(admin, `/api/v1/groups/${g2.id}/invites`, { role: "COMMANDER" })).code}/accept`);
  const ruiPaint = await rui.put("/api/v1/me/shifts/paint", { headers: H, data: { shiftTypeId: await typeId(rui, posto.id, "OC3"), dates: [DAY] } });
  expect(ruiPaint.ok()).toBeTruthy();

  // ── a Ana abre o link do convite, cria conta e entra no grupo ──
  await page.goto(`/convite/${invite.code}`);
  await page.getByRole("link", { name: "Criar conta" }).click();
  await page.locator("#fullName").fill("Ana Silva");
  await page.locator("#email").fill(`ana.${run}@gnr.test`);
  await page.locator("#password").fill(PASS);
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByText("Grupo 1").first()).toBeVisible();
  await shot(page, "01-convite");
  await page.getByRole("button", { name: "Entrar no grupo" }).click();
  await expect(page).toHaveURL(/\/grupo/);
  await expect(page.getByRole("heading", { name: "Grupo 1" })).toBeVisible();
  await shot(page, "02-grupo");

  // ── pinta AT2 em dois dias com o pincel ──
  await page.getByRole("link", { name: "Calendário" }).click();
  const monthOf = (d: string) => Number(d.slice(5, 7));
  if (monthOf(DAY) !== new Date().getMonth() + 1) await page.getByRole("button", { name: "Mês seguinte" }).click();
  await page.getByRole("button", { name: "Pintar dias" }).click();
  await page.locator(".brush", { hasText: "AT2" }).click();
  await page.locator(`[data-date="${DAY}"]`).click();
  await expect(page.locator(".paint-hint")).toHaveText(/A pintar/);
  await page.getByRole("button", { name: "OK" }).click();
  await expect(page.locator(`[data-date="${DAY}"] .pill`)).toHaveText("AT2");
  await shot(page, "03-calendario");

  // ── na escala do posto, pede troca ao Rui (outro grupo de folgas) ──
  await page.goto(`/posto?dia=${DAY}`);
  await expect(page.getByText("Patrulha (16h-00h)")).toBeVisible();
  await shot(page, "04-posto-dia");
  await page.getByRole("button", { name: /Cabo Rui Rocha/ }).click();
  await expect(page.getByRole("dialog", { name: "Pedir troca" })).toBeVisible();
  await page.locator("#swap-message").fill("Tenho tribunal nesse dia");
  await shot(page, "05-pedir-troca");
  await page.getByRole("button", { name: "Enviar pedido" }).click();
  await expect(page.getByRole("status")).toContainText("Pedido enviado");

  // ── o Rui entra, vê o pedido no Hoje e aceita ──
  const ruiCtx = await browser.newContext({ ...test.info().project.use, baseURL: "http://localhost:3000" });
  const ruiPage = await ruiCtx.newPage();
  await ruiPage.goto("/entrar");
  await ruiPage.locator("#email").fill(`rui.${run}@gnr.test`);
  await ruiPage.locator("#password").fill(PASS);
  await ruiPage.getByRole("button", { name: "Entrar" }).click();
  await expect(ruiPage.getByText("Pedidos de troca")).toBeVisible();
  await expect(ruiPage.getByRole("button", { name: "Notificações, 1 por ler" })).toBeVisible();
  await shot(ruiPage, "06-hoje-rui");
  await ruiPage.getByRole("button", { name: /Guarda Ana Silva/ }).first().click();
  await expect(ruiPage.getByText("“Tenho tribunal nesse dia”")).toBeVisible();
  await shot(ruiPage, "07-pedido-recebido");
  await ruiPage.getByRole("button", { name: "Aceitar" }).click();
  const doc = ruiPage.getByRole("link", { name: "Documento de troca" });
  await expect(doc).toBeVisible();
  await shot(ruiPage, "08-aceite");
  const pdf = await ruiPage.request.get((await doc.getAttribute("href"))!);
  expect(pdf.headers()["content-type"]).toBe("application/pdf");
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");

  // ── a escala da Ana mudou ──
  await page.goto("/calendario");
  if (monthOf(DAY) !== new Date().getMonth() + 1) await page.getByRole("button", { name: "Mês seguinte" }).click();
  await expect(page.locator(`[data-date="${DAY}"] .pill`)).toHaveText("OC3");
  await page.goto(`/grupo?s=trocas`);
  await expect(page.getByText("Aceite · documento emitido")).toBeVisible();
  await shot(page, "09-trocas-ana");
  await page.goto("/");
  await page.getByRole("button", { name: /Notificações/ }).click();
  await expect(page.getByText("Troca aceite")).toBeVisible();
  await shot(page, "10-notificacoes");
});
