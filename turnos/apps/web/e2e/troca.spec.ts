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

async function register(req: APIRequestContext, email: string, fullName: string, rank: string, inviteCode?: string) {
  return post(req, "/api/v1/auth/register", { email, password: PASS, fullName, rank, inviteCode });
}

async function login(page: Page, email: string, password = PASS) {
  await page.goto("/entrar");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
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
  await register(cmd1, `matos.${run}@gnr.test`, "Sofia Matos", "Cabo-Chefe", (await post(admin, `/api/v1/groups/${g1.id}/invites`, { role: "COMMANDER" })).code);
  const invite = await post(cmd1, `/api/v1/groups/${g1.id}/invites`, { email: `ana.${run}@gnr.test`, name: "Ana Silva", rank: "Guarda" });

  // Camarada do Grupo 2 com OC3 no dia da troca
  const rui = await playwright.request.newContext({ baseURL: "http://localhost:3000" });
  await register(rui, `rui.${run}@gnr.test`, "Rui Rocha", "Cabo", (await post(admin, `/api/v1/groups/${g2.id}/invites`, { role: "COMMANDER" })).code);
  const ruiPaint = await rui.put("/api/v1/me/shifts/paint", { headers: H, data: { shiftTypeId: await typeId(rui, posto.id, "OC3"), dates: [DAY] } });
  expect(ruiPaint.ok()).toBeTruthy();

  // ── a Ana abre o link do convite: o nome, o posto e o email já vêm preenchidos; cria conta e fica no grupo ──
  await page.goto(`/convite/${invite.code}`);
  await expect(page.getByText("Grupo 1").first()).toBeVisible();
  await expect(page.locator("#fullName")).toHaveValue("Ana Silva");
  await expect(page.locator("#email")).toHaveValue(`ana.${run}@gnr.test`);
  await page.locator("#password").fill(PASS);
  await shot(page, "01-convite");
  await page.getByRole("button", { name: "Criar conta e entrar" }).click();
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
  await login(ruiPage, `rui.${run}@gnr.test`);
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

test("link do grupo, nova palavra-passe dada pelo comandante e mudança de grupo", async ({ page, browser, playwright }) => {
  const r = `${run}b`;
  const admin = await playwright.request.newContext({ baseURL: "http://localhost:3000" });
  await register(admin, `admin@turnos.test`, "Administrador", "").catch(async () => {
    await post(admin, "/api/v1/auth/login", { email: "admin@turnos.test", password: PASS });
  });
  const posto = await post(admin, "/api/v1/postos", { name: `Posto Territorial de VRSA ${r}`, location: "VRSA" });
  const g1 = await post(admin, `/api/v1/postos/${posto.id}/groups`, { name: "Grupo 1" });
  const g2 = await post(admin, `/api/v1/postos/${posto.id}/groups`, { name: "Grupo 2" });
  const cmd2 = await playwright.request.newContext({ baseURL: "http://localhost:3000" });
  await register(cmd2, `cmd2.${r}@gnr.test`, "Paulo Sousa", "Cabo-Chefe", (await post(admin, `/api/v1/groups/${g2.id}/invites`, { role: "COMMANDER" })).code);

  // ── a comandante do Grupo 1 cria o link do grupo na app ──
  await register(page.request, `cmd1.${r}@gnr.test`, "Sofia Matos", "Cabo-Chefe", (await post(admin, `/api/v1/groups/${g1.id}/invites`, { role: "COMMANDER" })).code);
  await page.goto("/grupo");
  await page.getByRole("button", { name: "Membros" }).click();
  await page.getByRole("button", { name: "Link do grupo" }).click();
  const link = (await page.getByTestId("invite-code").textContent())!.trim();
  await shot(page, "11-link-do-grupo");

  // ── o Tiago abre o link, escreve os dados e entra ──
  const tiagoCtx = await browser.newContext({ ...test.info().project.use, baseURL: "http://localhost:3000" });
  const tiago = await tiagoCtx.newPage();
  await tiago.goto(`/convite/${link}`);
  await tiago.locator("#rank").selectOption("Guarda Principal");
  await tiago.locator("#fullName").fill("Tiago Reis");
  await tiago.locator("#email").fill(`tiago.${r}@gnr.test`);
  await tiago.locator("#password").fill(PASS);
  await tiago.getByRole("button", { name: "Criar conta e entrar" }).click();
  await expect(tiago).toHaveURL(/\/grupo/);
  await expect(tiago.getByRole("heading", { name: "Grupo 1" })).toBeVisible();

  // ── o Tiago esquece-se da palavra-passe: a comandante gera o código na ficha dele ──
  await page.reload();
  await page.getByRole("button", { name: "Membros" }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Guarda Principal Tiago Reis/ }).click();
  await page.getByRole("button", { name: "Código para nova palavra-passe" }).click();
  const code = (await page.getByTestId("reset-code").textContent())!.trim();
  await shot(page, "12-codigo-reposicao");

  await tiagoCtx.clearCookies();
  await tiago.goto("/entrar");
  await tiago.getByRole("link", { name: "Esqueci-me da palavra-passe" }).click();
  await tiago.locator("#reset-code").fill(code);
  await tiago.locator("#new-password").fill("nova-palavra-passe");
  await tiago.getByRole("button", { name: "Guardar e entrar" }).click();
  await expect(tiago.getByRole("heading", { name: "Hoje" })).toBeVisible();
  await tiagoCtx.clearCookies();
  await login(tiago, `tiago.${r}@gnr.test`, "nova-palavra-passe");
  await expect(tiago.getByRole("heading", { name: "Hoje" })).toBeVisible();

  // ── o comandante do Grupo 2 convida o Tiago, que muda de grupo ──
  const move = await post(cmd2, `/api/v1/groups/${g2.id}/invites`, {});
  await tiago.goto(`/convite/${move.code}`);
  await expect(tiago.getByText("Sais do")).toBeVisible();
  await tiago.getByRole("button", { name: "Mudar para o Grupo 2" }).click();
  await expect(tiago.getByRole("heading", { name: "Grupo 2" })).toBeVisible();
});
