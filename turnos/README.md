# Turnos

Calendário de serviços para militares da GNR, com escala do posto, grupos de folgas e trocas diretas entre camaradas
(sem autorização do comandante, com o documento oficial "Troca de Serviço" emitido na aceitação).

Desenho e arquitetura: [`../docs/turnos`](../docs/turnos). Especificação das trocas: [doc 09](../docs/turnos/09-trocas-gnr.md).

## Estrutura

```
turnos/
├── apps/api/          API Java 21 + Spring Boot 4 (monólito modular, Spring Modulith)
│   └── src/main/java/pt/turnos/
│       ├── identity/       registo, login, sessões (JWT em cookie + refresh rotativo)
│       ├── units/          posto, grupos de folgas, convites do comandante de grupo
│       ├── scheduling/     tipos de serviço, serviços dos militares, regras de compatibilidade
│       ├── swaps/          pedidos de troca, aceitação, documento PDF oficial, expiração na véspera
│       ├── notifications/  notificações in-app e Web Push (RFC 8291/8292, só JDK)
│       ├── importer/       migração de um posto do EscalasPT
│       ├── audit/          registo de auditoria
│       └── shared/         ids (UUIDv7), erros (RFC 9457), relógio
├── apps/web/          Next.js 16 (App Router): a app, com o design iOS do protótipo
├── contracts/openapi.json  contrato da API (fonte para o cliente do frontend)
└── infra/compose.yaml      PostgreSQL 18 para desenvolvimento
```

## Correr localmente

Requisitos: JDK 21 e Docker.

```bash
cd turnos
docker compose -f infra/compose.yaml up -d            # PostgreSQL 18 em localhost:5432

COOKIE_SECURE=false \
BOOTSTRAP_ADMIN_EMAIL=admin@exemplo.pt \
JWT_SECRET=$(head -c 48 /dev/urandom | base64) \
./gradlew :apps:api:bootRun
```

- `COOKIE_SECURE=false` só em `http://localhost` (em produção os cookies usam os prefixos `__Host-`/`__Secure-`).
- Só se cria conta com convite. A exceção é o email de `BOOTSTRAP_ADMIN_EMAIL`, que se regista sem convite e fica
  administrador: cria postos e grupos de folgas e convida o comandante de cada grupo.
- Todos os pedidos que alteram dados levam o cabeçalho `X-Requested-With: turnos`.
- Contrato: `GET /api/v3/api-docs`.

A app web (noutro terminal):

```bash
cd apps/web
pnpm install
pnpm dev            # http://localhost:3000 (o /api é encaminhado para a API em localhost:8080)
```

### Notificações no telemóvel (Web Push)

Gerar as chaves VAPID uma vez (`npx web-push generate-vapid-keys`) e arrancar a API com
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` e `VAPID_SUBJECT=mailto:…`. Sem chaves, só há notificações dentro da app.
No iPhone, o push só funciona com a app adicionada ao ecrã principal.

## Importar um posto do EscalasPT

```bash
java -jar apps/api/build/libs/api-0.1.0-SNAPSHOT.jar \
  --turnos.import.escalaspt.url=jdbc:postgresql://HOST:5432/gnr_escalas \
  --turnos.import.escalaspt.user=… --turnos.import.escalaspt.password=… \
  --turnos.import.station-code=PT-CMR \
  --turnos.import.group-name="Grupo 1" \
  --turnos.import.commander-email=comandante.grupo@exemplo.pt \
  --turnos.import.from=2026-09-01
```

Cria o posto, os tipos de serviço, os militares (entram com a mesma palavra-passe; o hash passa a Argon2 no primeiro
login) e os serviços publicados desde `from`, todos no grupo de folgas indicado. Serviços incompatíveis (ex.: dois
serviços normais no mesmo dia) não são importados e aparecem no relatório. Não migra hierarquia, papéis de comandante,
rascunhos, trocas nem notificações. Como o EscalasPT não guarda o posto (patente), cada militar completa-o no perfil.

## Testes

```bash
./gradlew :apps:api:test                       # API: unitários, integração (Testcontainers), módulos, contrato
cd apps/web && pnpm typecheck && pnpm lint && pnpm build
pnpm test:e2e                                  # ponta a ponta (precisa da API a correr, ver acima)
```

Se a API mudar: `UPDATE_CONTRACT=1 ./gradlew :apps:api:test --tests '*OpenApiContract*'` e depois `pnpm gen:api` na web.

Os testes de integração arrancam um PostgreSQL 18 real (Testcontainers): as regras que vivem na base de dados
(sobreposição de serviços com `EXCLUDE`, um pedido ativo por serviço) são testadas a sério, incluindo trocas concorrentes.

## Contas e grupos de folgas

1. O **administrador** cria o posto e os grupos e envia a cada comandante de grupo o seu convite (link `/convite/<código>`).
2. O **comandante de grupo** abre o link, cria conta e fica comandante. Em *Grupo → Membros* convida os militares:
   - **convite pessoal** (posto, nome e email opcional): uso único; o militar encontra os dados já preenchidos;
   - **link do grupo**: um link para o grupo todo, até 30 militares durante 7 dias; um novo link desativa o anterior.
3. O **militar** abre o link, cria conta e fica logo no grupo. Se já tem conta, entra e aceita. Um convite de outro grupo
   do mesmo posto muda-o de grupo (a escala e as trocas continuam); para ir para outro posto, sai primeiro do grupo.
4. **Palavra-passe esquecida:** na ficha do militar, o comandante de grupo gera um código (uso único, 24 h) e envia-o;
   o militar usa-o em *Entrar → Esqueci-me da palavra-passe*. O código do comandante é gerado pelo administrador.
   Repor termina as sessões abertas e desbloqueia a conta.
5. No **perfil**, cada militar muda a palavra-passe (termina as outras sessões) e pode sair do grupo. O comandante de
   grupo passa o comando na ficha de outro militar antes de sair.

## Fluxo principal pela API

```http
POST /api/v1/auth/register                     (admin de arranque) { email, password, fullName }
POST /api/v1/postos                            (admin) { name, location }
POST /api/v1/postos/{postoId}/groups           (admin) { name: "Grupo 2" }
POST /api/v1/groups/{groupId}/invites          (comandante de grupo) { email, name, rank } → { code }
                                               link do grupo: { maxUses: 30 }
GET  /api/v1/invites/{code}                    (público) grupo e dados pré-preenchidos
POST /api/v1/auth/register                     { inviteCode, email, password, fullName, rank, serviceNumber }
POST /api/v1/invites/{code}/accept             (militar que já tem conta; muda de grupo no mesmo posto)
POST /api/v1/groups/{groupId}/members/{userId}/password-reset   (comandante de grupo) → { code }
POST /api/v1/auth/password-reset               { code, password }
POST /api/v1/me/password                       { currentPassword, newPassword }
PUT  /api/v1/me/shifts/paint                   { shiftTypeId, dates: ["2026-10-07", …] }
GET  /api/v1/postos/{postoId}/shifts?from&to[&groupId]      escala do posto / do grupo
POST /api/v1/swaps                             { shiftId, targetShiftId, message }
POST /api/v1/swaps/{id}/accept | hold | decline | cancel
GET  /api/v1/swaps/{id}/document.pdf
```
