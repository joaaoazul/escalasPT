# 4. API

## 4.1 Convenções

| Tema | Regra |
|------|-------|
| Base | `/api/v1` — versão no path; *breaking changes* só em `/v2` |
| Formato | JSON UTF-8, `camelCase`; datas locais `YYYY-MM-DD`, horas locais `HH:mm`, instantes ISO-8601 UTC (`2026-10-24T21:00:00Z`), durações em minutos (inteiro) |
| Recursos | Substantivos no plural; ações não-CRUD como sub-recurso com `:` (`/days:paint`, `/swaps/{id}:accept`) — estilo Google AIP-136 |
| Paginação | Por cursor: `?limit=50&cursor=…` → `{ items: [...], nextCursor }` (ids v7 são ordenáveis) |
| Intervalos | `?from=2026-10-01&to=2026-11-01` — **semiaberto** `[from, to)`, em datas locais do calendário |
| Concorrência | `ETag`/`If-Match` com a `version` do recurso em `PATCH`/`DELETE`; `409` se divergir |
| Cache | `ETag` + `If-None-Match` em leituras de intervalo → `304` |
| Idempotência | `Idempotency-Key: <uuid>` aceite em todos os `POST` e nas ações em lote |
| Erros | **RFC 9457 Problem Details** (`application/problem+json`) |
| Autenticação | Cookie `__Host-turnos_at` (JWT curto) + `__Host-turnos_rt` (refresh, path `/api/v1/auth`); em clientes nativos, `Authorization: Bearer` |
| CSRF | Cookies `SameSite=Strict` + header `X-Requested-With: turnos` obrigatório em métodos não seguros (ver doc 06) |
| Rate limiting | Headers `RateLimit-Policy` / `RateLimit` (draft IETF); `429` com `Retry-After` |
| Rastreio | `X-Request-Id` devolvido sempre (e aceite do cliente) — aparece nos logs e nos Problem Details |

### Formato de erro

```json
{
  "type": "https://turnos.pt/problems/shift-conflict",
  "title": "O turno entra em conflito com outros turnos",
  "status": 422,
  "detail": "2 conflitos encontrados",
  "instance": "/api/v1/calendars/0192…/days:paint",
  "requestId": "01J9ZB…",
  "violations": [
    {
      "code": "OVERLAP",
      "severity": "ERROR",
      "date": "2026-10-12",
      "conflictingShiftId": "0192…",
      "message": "Sobreposição com N (22:00–06:00)"
    },
    {
      "code": "MIN_REST",
      "severity": "WARNING",
      "date": "2026-10-13",
      "params": { "restHours": 8, "minRestHours": 11 },
      "message": "Apenas 8 h de descanso (mínimo 11 h)"
    }
  ]
}
```

- Os `code`s são estáveis (o frontend traduz por código; `message` é *fallback* no locale do utilizador).
- **Avisos não bloqueiam**: pedidos com apenas `WARNING` gravam e devolvem `200` com `warnings[]`.
  O cliente pode pedir `?dryRun=true` para validar sem gravar (usado na pré-visualização de rotações).

Catálogo de `type`s: `validation`, `not-found`, `forbidden`, `version-conflict`, `shift-conflict`,
`swap-invalid-state`, `rate-limited`, `idempotency-mismatch`, `auth-required`, `mfa-required`.

## 4.2 Endpoints

### Auth & conta (`identity`)

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/auth/register` | `{email, password, displayName, locale, timeZone}` → envia email de verificação |
| POST | `/auth/verify-email` | `{token}` |
| POST | `/auth/login` | `{email, password}` → cookies; ou `401 mfa-required` com `mfaToken` |
| POST | `/auth/login/mfa` | `{mfaToken, code}` (TOTP) |
| POST | `/auth/passkeys/options` · `/auth/passkeys/verify` | Login com passkey (WebAuthn) |
| GET | `/auth/oidc/{provider}/authorize` · `/auth/oidc/{provider}/callback` | Google / Apple (PKCE) |
| POST | `/auth/refresh` | Roda o refresh token (cookie) |
| POST | `/auth/logout` | Revoga a sessão atual |
| POST | `/auth/password/forgot` · `/auth/password/reset` | Recuperação |
| GET / PATCH | `/me` | Perfil, locale, fuso, início da semana |
| GET | `/me/sessions` · DELETE `/me/sessions/{id}` | Dispositivos ativos |
| POST / DELETE | `/me/mfa/totp` | Ativar (devolve `otpauth://` + QR) / desativar |
| GET / POST / DELETE | `/me/passkeys[/{id}]` | Gerir passkeys |
| POST | `/me/export` | Gera ZIP com todos os dados (RGPD, art. 20.º) → link por email |
| DELETE | `/me` | Apaga/anonimiza conta (com confirmação por password/passkey) |

### Calendários, tipos e turnos (`calendar`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/calendars` | Os meus + partilhados comigo (com `permission`) |
| POST | `/calendars` | Cria; `?template=DEFAULT` gera tipos iniciais |
| GET / PATCH / DELETE | `/calendars/{calId}` | Inclui `rules` (descanso mínimo, dia inteiro exclusivo, máx. horas) |
| GET / PUT / DELETE | `/calendars/{calId}/shares[/{userId}]` | Partilha direta (`AVAILABILITY`/`VIEW`/`EDIT`) |
| GET / POST | `/calendars/{calId}/shift-types` | Lista / cria tipo |
| PATCH / DELETE | `/calendars/{calId}/shift-types/{id}` | `DELETE` arquiva se houver turnos |
| POST | `/calendars/{calId}/shift-types/{id}:apply-to-future` | Propaga horário novo a turnos futuros deste tipo |
| PUT | `/calendars/{calId}/shift-types:reorder` | `{ids: [...]}` |
| **GET** | **`/calendars/{calId}/shifts?from&to`** | Turnos no intervalo (+ `holidays[]`, `notes[]` com `?include=holidays,notes`) |
| POST | `/calendars/{calId}/shifts` | Turno pontual `{date, shiftTypeId?, start?, durationMinutes?, allDay?, notes?, overtimeMinutes?}` |
| GET / PATCH / DELETE | `/shifts/{id}` | `If-Match` obrigatório em PATCH/DELETE |
| **PUT** | **`/calendars/{calId}/days:paint`** | Modo pincel: `{shiftTypeId \| null, dates: [...], mode: REPLACE \| ADD}` — `null` limpa os dias |
| POST | `/calendars/{calId}/shifts:batch` | Operações mistas `{create[], update[], delete[]}` atómicas (usado por desfazer/refazer e drag&drop) |
| POST | `/calendars/{calId}/shifts:validate` | Valida um conjunto hipotético (sem gravar) |
| GET / PUT / DELETE | `/calendars/{calId}/notes/{date}` | Nota de dia |
| GET / POST / DELETE | `/calendars/{calId}/holidays[/{date}]` | Feriados efetivos (catálogo + personalizados) / personalizados |

**Exemplo — resposta de `GET /calendars/{id}/shifts?from=2026-10-01&to=2026-11-01&include=holidays`**

```json
{
  "calendar": { "id": "0192…", "timeZone": "Europe/Lisbon", "version": 7 },
  "shifts": [
    {
      "id": "0192…a1",
      "date": "2026-10-24",
      "shiftTypeId": "0192…t3",
      "allDay": false,
      "start": "22:00",
      "durationMinutes": 480,
      "startsAt": "2026-10-24T21:00:00Z",
      "endsAt": "2026-10-25T05:00:00Z",
      "effective": { "name": "Noite", "abbreviation": "N", "color": "#1E293B", "kind": "WORK", "breakMinutes": 30 },
      "notes": null,
      "overtimeMinutes": 0,
      "source": "ROTATION",
      "isOverride": false,
      "pendingSwap": null,
      "version": 0
    }
  ],
  "holidays": [ { "date": "2026-10-05", "name": "Implantação da República", "kind": "NATIONAL" } ]
}
```

> `effective` resolve herança tipo→turno no servidor, para o cliente nunca ter de reimplementar a regra.
> Note-se o turno de 24/10 (noite da mudança de hora): 8 h reais terminam às 05:00 locais.

### Rotações (`rotation`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET / POST | `/calendars/{calId}/rotations` | `{name, steps: [shiftTypeId \| null, …]}` (o comprimento define o ciclo) |
| GET / PATCH / DELETE | `/rotations/{id}` | |
| POST | `/rotations/{id}:preview` | `{from, to, startOffset}` → turnos propostos + conflitos, sem gravar |
| POST | `/rotations/{id}:apply` | `{from, to, startOffset, onConflict: SKIP \| REPLACE \| ABORT}` → `{applicationId, created, skipped[], warnings[]}` |
| GET | `/calendars/{calId}/rotation-applications` | Histórico de aplicações |
| POST | `/rotation-applications/{id}:reapply` | Regenera preservando `isOverride` |
| DELETE | `/rotation-applications/{id}` | Remove turnos gerados (não-override) |
| GET | `/rotation-templates` | Biblioteca de padrões comuns (4×4, Pitman, 24×48…) |

### Horas, remuneração e ausências (`timeaccounting`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET / PUT | `/calendars/{calId}/pay-profile` | Taxa base, majorações, objetivo mensal |
| GET | `/calendars/{calId}/stats?from&to&groupBy=day\|week\|month` | Horas totais/noturnas/fim de semana/feriado/extra, por tipo, valor estimado |
| GET | `/calendars/{calId}/stats/year/{year}` | Heatmap + totais anuais |
| GET / PUT | `/calendars/{calId}/allowances/{year}` | Saldos de ausências (atribuídos / usados / planeados / restantes) |

```json
{
  "period": { "from": "2026-10-01", "to": "2026-11-01" },
  "totals": {
    "workedMinutes": 9600, "nightMinutes": 2880, "weekendMinutes": 1920,
    "holidayMinutes": 480, "overtimeMinutes": 120, "shifts": 20,
    "estimatedPay": { "amount": "1843.20", "currency": "EUR" },
    "targetMinutes": 9360, "balanceMinutes": 240
  },
  "byType": [ { "shiftTypeId": "…", "count": 6, "workedMinutes": 2880 } ],
  "series": [ { "bucket": "2026-10-01", "workedMinutes": 480 } ]
}
```

> Dinheiro como **string decimal** (nunca `float`). No backend: `BigDecimal` com `RoundingMode.HALF_EVEN`.

### Grupos (`groups`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET / POST | `/groups` | Os meus grupos / criar (quem cria é `OWNER`) |
| GET / PATCH / DELETE | `/groups/{gid}` | Nome, cor, `swapPolicy` (só OWNER/ADMIN) |
| GET | `/groups/{gid}/members` | |
| PATCH / DELETE | `/groups/{gid}/members/{userId}` | Mudar papel / remover (ou sair, se for o próprio) |
| PUT | `/groups/{gid}/members/me/share` | `{calendarId, shareLevel}` — que calendário partilho |
| POST | `/groups/{gid}/owner:transfer` | `{userId}` |
| GET / POST / DELETE | `/groups/{gid}/invites[/{id}]` | Link (`maxUses`, `expiresAt`) ou email |
| GET | `/invites/{token}` | Pré-visualização pública mínima (nome do grupo, nº membros) |
| POST | `/invites/{token}:accept` | Entrar no grupo |
| **GET** | **`/groups/{gid}/roster?from&to`** | Matriz membros × dias |
| GET | `/groups/{gid}/now` | Quem está em turno agora / hoje / amanhã |
| GET | `/groups/{gid}/activity?cursor` | Registo de atividade (auditoria do grupo) |

### Trocas (`swaps`)

> **Escalas GNR:** usam a API de [9.9](09-trocas-gnr.md#99-api-substitui-a-secção-trocas-do-doc-04)
> (`:accept`, `:hold`, `:decline`, `:cancel`, `document.pdf`, `/verify/{code}`), sem `:approve`/`:reject`.

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/groups/{gid}/swaps` | `{kind: SWAP\|GIVEAWAY, shiftId, targetUserId?, targetShiftId?, message?}` — sem `targetUserId` ⇒ oferta aberta |
| GET | `/groups/{gid}/swaps?status&mine=true` | Lista |
| GET | `/me/swaps?role=requester\|target&status=` | As minhas trocas em todos os grupos |
| GET | `/swaps/{id}` | Detalhe (inclui validação prévia do impacto nos dois calendários) |
| POST | `/swaps/{id}/responses` | Responder a oferta aberta `{offeredShiftId?}` |
| POST | `/swaps/{id}/responses/{rid}:choose` | Autor escolhe uma resposta → `PENDING_PEER`/`PENDING_APPROVAL`/`COMPLETED` |
| POST | `/swaps/{id}:accept` · `:decline` | Colega-alvo responde |
| POST | `/swaps/{id}:approve` · `:reject` | Admin do grupo (apenas com `ADMIN_APPROVAL`) |
| POST | `/swaps/{id}:cancel` | Autor |
| GET | `/swaps/{id}/receipt.pdf` | Comprovativo |

Todas as transições devolvem o recurso completo atualizado e `409 swap-invalid-state` se o estado já mudou.

### Notificações (`notifications`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/notifications?cursor&unread=true` | |
| POST | `/notifications:mark-read` | `{ids: [...]}` ou `{all: true, before}` |
| GET / PUT | `/me/notification-preferences` | Matriz tipo × canal, horas de silêncio |
| GET | `/push/vapid-public-key` | |
| POST / DELETE | `/push/subscriptions` | Registar/remover subscrição Web Push do dispositivo |
| GET | `/stream` | **SSE** — eventos em tempo real para o utilizador autenticado |

### Exportação e integrações (`exchange`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET / POST | `/calendars/{calId}/ics-feeds` | Cria feed → devolve **uma vez** o URL `webcal://turnos.pt/ics/{token}.ics` |
| DELETE | `/calendars/{calId}/ics-feeds/{id}` | Revoga |
| GET | `/ics/{token}.ics` | **Público** (token = segredo de 256 bits), `text/calendar`, `ETag`, `Cache-Control: private, max-age=900` |
| GET | `/calendars/{calId}/export.pdf?month=2026-10` | Mês em PDF (A4, legenda, totais) |
| GET | `/calendars/{calId}/export.csv?from&to` | |
| POST | `/calendars/{calId}/import` | `multipart` CSV/ICS → pré-visualização → `:commit` (v1.1+) |

### Sistema

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/actuator/health/liveness` · `/readiness` | Só na rede interna |
| GET | `/actuator/prometheus` | Só na rede interna |
| GET | `/v3/api-docs` · `/swagger-ui` | Apenas em dev/staging |

## 4.3 Eventos em tempo real (SSE)

| `event` | `data` | Quem recebe | Ação no cliente |
|---------|--------|-------------|-----------------|
| `shifts.changed` | `{calendarId, from, to}` | Dono + partilhados + membros de grupos onde o calendário é partilhado | Invalidar `['shifts', calendarId]` sobrepostos e `['roster', gid]` |
| `calendar.changed` | `{calendarId}` | Idem | Invalidar tipos/regras |
| `swap.updated` | `{swapId, groupId, status}` | Envolvidos + admins do grupo | Invalidar `['swaps', …]`, toast |
| `group.changed` | `{groupId}` | Membros | Invalidar membros/roster |
| `notification.created` | `{id, type}` | Destinatário | Incrementar badge, invalidar lista |
| `session.revoked` | `{}` | Dispositivo cuja sessão foi revogada | Logout imediato |
| `ping` | — | Todos (a cada 25 s) | Manter ligação viva através de proxies |

## 4.4 Feed ICS

- `VCALENDAR` com `X-WR-CALNAME`, `X-WR-TIMEZONE` e `VTIMEZONE` gerado pelo ical4j para o fuso do calendário.
- Cada turno = `VEVENT` com `UID = {shiftId}@turnos.pt` (estável → os clientes atualizam em vez de duplicar),
  `DTSTART;TZID=Europe/Lisbon`, `SUMMARY = "N · Noite"`, `CATEGORIES = kind`, `VALARM` opcional.
- Turnos de dia inteiro: `DTSTART;VALUE=DATE`.
- Janela: 3 meses para trás, 12 para a frente (Google Calendar refresca a cada ~12–24 h; está documentado ao utilizador).
- Nível `AVAILABILITY`: `SUMMARY = "Ocupado"`, sem notas.

## 4.5 Evolução do contrato

- O OpenAPI é gerado do código (springdoc) e *commitado* em `contracts/openapi.yaml`.
- CI corre **oasdiff** entre `main` e o PR: *breaking changes* em `/v1` falham o build.
- Campos novos são sempre opcionais; o cliente ignora campos desconhecidos.
