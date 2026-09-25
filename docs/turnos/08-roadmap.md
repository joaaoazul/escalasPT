# 8. Roadmap e plano de execução

Estimativas para **1 dev full-stack** a tempo inteiro (dividir aproximadamente por 1,7 com dois devs). Cada fase termina com algo utilizável.

## Fase 0 — Fundações (semana 1–2)

- Monorepo (`apps/api`, `apps/web`, `contracts`, `infra`), Gradle + version catalog, pnpm workspaces.
- Spring Boot 4 esqueleto com módulos vazios + `ApplicationModules.verify()`, Flyway `V1`, Testcontainers, ProblemDetail advice, `Clock` injetado.
- Next.js 16 esqueleto: shell (sidebar/tab bar), tema claro/escuro, tokens, shadcn/ui, next-intl, cliente gerado do OpenAPI.
- `compose.yaml` de dev (postgres 18, redis, mailpit), CI (`ci-api`, `ci-web`, `contract`), Renovate.
- **Saída**: `docker compose up` → página de login a falar com `/api/v1/health`; pipeline verde.

## Fase 1 — Conta e calendário pessoal (semana 3–6) → *alpha interna*

- `identity`: registo, verificação de email, login, refresh rotativo, logout, sessões, lockout, rate limit.
- `calendar`: calendários, tipos de turno (com modelos iniciais), turnos, notas; **modelo temporal completo com testes DST**.
- `rules`: sobreposição (BD), dia inteiro, descanso mínimo; Problem Details com `violations[]`.
- `holidays`: catálogo PT nacional + municipal (dataset versionado em `resources/holidays/pt/*.csv`, Páscoa calculada).
- Web: `MonthGrid`, detalhe de dia, editor de turno, **modo pincel com optimistic update e desfazer**, vista agenda, gestão de tipos.
- **Saída**: uma pessoa regista-se e preenche o mês em < 1 min.

## Fase 2 — Rotações, horas e integrações (semana 7–9) → *beta fechada*

- `rotation`: CRUD, pré-visualização, aplicar com SKIP/REPLACE, reaplicar preservando overrides, biblioteca de modelos.
- `timeaccounting`: estatísticas de horas (total/noturno/FDS/feriado/extra).
- `exchange`: feed ICS com tokens; export PDF do mês.
- `notifications`: centro in-app, SSE, Web Push, lembretes (db-scheduler), preferências básicas.
- Web: assistente de rotação, `TimeGrid` (semana/dia), página "Hoje", estatísticas, PWA (Serwist) com leitura offline.
- **Saída**: beta com 20–50 utilizadores reais (ex.: colegas do EscalasPT).

## Fase 3 — Grupos e trocas (semana 10–13) → **MVP público**

- `groups`: criar, convites (link/email), papéis, partilha de calendário com nível de detalhe, roster, "quem está agora".
- `swaps`: troca direta, máquina de estados completa, política do grupo, expiração, concorrência testada.
- `audit`: atividade do grupo.
- Web: roster virtualizado, caixa de entrada de trocas, cartões de troca, notificações push com ações.
- Segurança: TOTP, exportação/apagamento de dados (RGPD), CSP com nonces, testes de matriz de autorização.
- E2E Playwright do fio condutor; testes de carga básicos (k6: 200 utilizadores simultâneos a navegar meses).
- **Saída**: lançamento público.

## Fase 4 — v1.1 (semana 14–18)

- Ofertas abertas ao grupo (`GIVEAWAY`, respostas múltiplas), comprovativo PDF.
- Perfil remuneratório completo, banco de horas, saldos de ausências.
- Passkeys, login Google/Apple.
- Vista anual (heatmap), drag & drop no desktop, ⌘K.
- Email: convites, resumo semanal opcional.
- Export CSV; RLS como defesa em profundidade.

## Mais tarde (backlog priorizado)

1. Importação CSV/ICS (e **importador do EscalasPT**, ver abaixo).
2. App nativa (Expo/React Native) reutilizando a API e o design system (tokens partilhados).
3. Widgets (iOS/Android) "próximo turno".
4. Mutações offline com fila e resolução de conflitos.
5. *Teams Pro* (opcional, pago): cobertura mínima por dia, planeamento por um coordenador, exportação para processamento salarial.
6. Outros países (feriados, locale).

## Plano de migração a partir do EscalasPT

O EscalasPT continua a funcionar para o posto atual enquanto o Turnos amadurece. Migração opcional e por utilizador:

| EscalasPT | Turnos |
|-----------|--------|
| `users` (militar) | `users` (email, `full_name` → `display_name`); NIP/número de ordem **não** migram |
| `stations` | → um **grupo** por posto (opcional), com o antigo comandante como `ADMIN` e `swap_policy = ADMIN_APPROVAL` |
| `shift_types` (por posto) | → copiados para o calendário de cada membro; `is_absence` → `kind = ABSENCE`, `F` → `kind = OFF`, `GRAT` → `WORK` |
| `shifts` (status `published`) | → `shifts` no calendário pessoal, `source = IMPORT`; `draft`/`cancelled` não migram |
| `shift_swap_requests` (`approved`) | → histórico de auditoria do grupo (não como trocas ativas) |
| `notifications`, `audit_logs` | Não migram |

Ferramenta: comando `turnos-migrate` (Spring Boot `CommandLineRunner` num perfil próprio) que lê diretamente da BD do EscalasPT
e escreve via serviços de domínio (as regras e constraints aplicam-se; conflitos ficam num relatório).

## Riscos e mitigação

| Risco | Prob. | Impacto | Mitigação |
|-------|-------|---------|-----------|
| Bugs de tempo (DST, noites, fusos) | Alta | Alto | Modelo explícito (ADR-006), tabelas de teste, *property-based testing* |
| Componentes de calendário próprios atrasam | Média | Médio | Começar pelo `MonthGrid` (o essencial); `TimeGrid` pode usar Schedule-X temporariamente |
| Next.js + Spring = duas stacks para uma pessoa | Média | Médio | Next "fino" (ADR-003), contrato gerado, CI separado por app |
| Feriados municipais incompletos/errados | Média | Baixo | Dataset versionado + feriados personalizados + reporte de erro na UI |
| Entregabilidade de push no iOS (PWA tem de estar instalada) | Alta | Médio | Onboarding que explica "Adicionar ao ecrã principal"; email como *fallback*; app nativa no roadmap |
| Adoção de grupos baixa | Média | Médio | Valor individual primeiro; convites com pré-visualização e 1 toque |

## Definição de "pronto" (por funcionalidade)

- Endpoint no contrato OpenAPI, testes unitários + integração + autorização.
- UI em pt-PT e en, claro/escuro, 360 px e desktop, navegação por teclado, sem erros axe.
- Eventos/efeitos secundários idempotentes; métricas e logs úteis.
- Documentação atualizada (este diretório + ADR se houve decisão nova).
