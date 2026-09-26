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
│       ├── audit/          registo de auditoria
│       └── shared/         ids (UUIDv7), erros (RFC 9457), relógio
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
- O primeiro registo com o email de `BOOTSTRAP_ADMIN_EMAIL` fica administrador: é quem cria postos e grupos de folgas
  e nomeia o comandante de cada grupo (convite com `"role": "COMMANDER"`).
- Todos os pedidos que alteram dados levam o cabeçalho `X-Requested-With: turnos`.
- Contrato: `GET /api/v3/api-docs`.

## Testes

```bash
./gradlew :apps:api:test
```

Os testes de integração arrancam um PostgreSQL 18 real (Testcontainers): as regras que vivem na base de dados
(sobreposição de serviços com `EXCLUDE`, um pedido ativo por serviço) são testadas a sério, incluindo trocas concorrentes.

## Fluxo principal pela API

```http
POST /api/v1/auth/register                     { email, password, fullName, rank, serviceNumber }
POST /api/v1/postos                            (admin) { name, location }
POST /api/v1/postos/{postoId}/groups           (admin) { name: "Grupo 2" }
POST /api/v1/groups/{groupId}/invites          (comandante de grupo) { email } → { code }
POST /api/v1/invites/{code}/accept             (militar convidado)
PUT  /api/v1/me/shifts/paint                   { shiftTypeId, dates: ["2026-10-07", …] }
GET  /api/v1/postos/{postoId}/shifts?from&to[&groupId]      escala do posto / do grupo
POST /api/v1/swaps                             { shiftId, targetShiftId, message }
POST /api/v1/swaps/{id}/accept | hold | decline | cancel
GET  /api/v1/swaps/{id}/document.pdf
```
