# 7. Registo de decisões de arquitetura (ADR)

Formato curto: **Contexto → Decisão → Consequências → Alternativas rejeitadas**. Estado: *Proposta* até ao arranque do projeto.

---

## ADR-001 — Monólito modular em vez de microserviços
- **Contexto**: equipa pequena, domínio coeso (quase tudo gira à volta de "turnos"), transações que atravessam agregados (trocas mexem em dois calendários).
- **Decisão**: um único serviço Spring Boot com módulos verificados pelo **Spring Modulith**; eventos entre módulos com outbox.
- **Consequências**: um deploy, uma BD, transações ACID simples. Se um módulo precisar de escalar à parte (ex.: `notifications`),
  os eventos já existem — extrair é mover o *listener* para outro processo.
- **Rejeitadas**: microserviços (custo operacional e consistência distribuída sem benefício); monólito sem fronteiras (degrada com o tempo).

## ADR-002 — Java 25 + Spring Boot 4 com virtual threads (sem WebFlux)
- **Contexto**: pedido explícito de backend Java; SSE e chamadas externas (push, email) são I/O intensivas.
- **Decisão**: Spring MVC clássico com `spring.threads.virtual.enabled=true`.
- **Consequências**: código imperativo, fácil de depurar e testar; milhares de ligações SSE sem *thread pool* dedicado.
  Cuidado com `synchronized` em caminhos quentes (*pinning*, já muito reduzido no JDK 24+).
- **Rejeitadas**: WebFlux/Reactor (complexidade sem ganho real para este volume); Quarkus/Micronaut (bons, mas ecossistema e familiaridade favorecem Spring).

## ADR-003 — Next.js (App Router) como frontend, sem lógica de negócio
- **Contexto**: pedido "React ou Next.js"; precisamos de landing page + app; futura app nativa.
- **Decisão**: Next.js 16 com RSC só para *layout*/*prefetch*; mutações diretas à API Java.
- **Consequências**: uma só fonte de regras (Java). Next.js é "apenas" UI + SSR. Porta aberta a React Native a consumir a mesma API.
- **Rejeitadas**: Vite SPA pura (perde SSR/landing no mesmo projeto, mas seria uma alternativa válida e mais simples — reavaliar se o SSR não trouxer valor);
  BFF em Next com Server Actions (duplicaria autorização e validação).

## ADR-004 — PostgreSQL com invariantes na base de dados
- **Contexto**: sobreposição de turnos e trocas concorrentes são os bugs mais caros; o EscalasPT fazia a verificação só em Python.
- **Decisão**: `EXCLUDE USING gist` para sobreposição, `UNIQUE` parciais (um dia inteiro por dia; um pedido ativo por turno), `CHECK`s, `@Version`.
- **Consequências**: impossível corromper dados mesmo com bugs ou corridas; testes de integração têm de usar Postgres real (Testcontainers).
  Erros de constraint são traduzidos para Problem Details amigáveis num `@ControllerAdvice`.
- **Rejeitadas**: validação só em código (race conditions); *advisory locks* manuais.

## ADR-005 — Turnos materializados; rotações como gerador
- Ver [3.4](03-modelo-de-dados.md#34-decisões-de-modelação-explicadas).
- **Rejeitada**: expansão em leitura estilo RRULE.

## ADR-006 — Tempo local + duração → instantes UTC calculados no servidor
- **Contexto**: turnos noturnos, DST, vários fusos em Portugal (continente, Açores).
- **Decisão**: o utilizador define `data + início + duração` no fuso do calendário; o servidor grava `starts_at/ends_at` (UTC). Regra de fim `ELAPSED` (por omissão) ou `WALL_CLOCK` por tipo.
- **Consequências**: todas as contas de horas são sobre instantes reais; a UI mostra sempre no fuso **do calendário** (não do browser).
- **Rejeitadas**: guardar só `start_time/end_time` locais (ambíguo em DST); guardar só UTC (perde a intenção "às 22:00").

## ADR-007 — Contrato OpenAPI como fonte de verdade e cliente TS gerado
- **Decisão**: springdoc gera o contrato → *commit* em `contracts/` → `openapi-typescript` gera tipos → `openapi-fetch`.
- **Consequências**: sem tipos escritos à mão a dessincronizar (problema recorrente no EscalasPT com `types/index.ts`); *breaking changes* visíveis em PR.
- **Rejeitadas**: GraphQL (sobre-engenharia para este domínio); tRPC (exige TS no backend).

## ADR-008 — SSE em vez de WebSocket
- **Decisão**: `GET /api/v1/stream` com `SseEmitter`; fan-out por Redis pub/sub.
- **Consequências**: mais simples de operar (HTTP normal, reconexão nativa com `Last-Event-ID`); só servidor→cliente, que é tudo o que precisamos.
- **Rejeitadas**: WebSocket/STOMP (bidirecional desnecessário; o EscalasPT teve lacunas de WS/logs que exigiram correções).

## ADR-009 — Outbox (Spring Modulith event publication registry) para efeitos secundários
- **Decisão**: notificações, auditoria, lembretes e invalidações SSE reagem a eventos persistidos na mesma transação.
- **Consequências**: nenhum efeito perdido se o processo cair entre o *commit* e o envio; *listeners* têm de ser idempotentes.
- **Rejeitadas**: chamar serviços de notificação dentro da transação (acoplamento + perdas); Kafka/RabbitMQ (infraestrutura extra desnecessária).

## ADR-010 — Jobs persistentes com db-scheduler
- **Decisão**: lembretes, expiração de trocas, limpezas e *rolling window* de lembretes no **db-scheduler** (tabela Postgres).
- **Consequências**: sobrevivem a reinícios, seguros com várias réplicas, sem novo componente.
- **Rejeitadas**: `@Scheduled` em memória (perde tarefas); Quartz (mais pesado); JobRunr (bom, licença Pro para algumas funcionalidades).

## ADR-011 — Sem hierarquia organizacional; colaboração por grupos e partilhas
- **Contexto**: requisito "sem postos e comandantes".
- **Decisão**: posse individual de calendários; `groups` horizontais com papéis `OWNER/ADMIN/MEMBER` só para gestão do grupo;
  aprovação de trocas é **política do grupo** (`PEER_ONLY`, `ADMIN_APPROVAL`, `DISABLED`); planeamento por terceiros só via share `EDIT`.
- **Consequências**: produto útil a uma pessoa sozinha; nenhuma entidade "empresa" para configurar. Casos empresariais (cobertura mínima,
  planeamento centralizado, aprovação hierárquica) ficam fora do âmbito — podem voltar como módulo *Teams Pro* sem mexer no núcleo.
- **Rejeitadas**: manter `Station` renomeada para "Organização" (reintroduz o modelo *top-down* que se quer abandonar).

## ADR-012 — Autenticação própria com cookies `__Host-` (sem IdP externo no MVP)
- **Decisão**: Spring Security emite JWT curto + refresh rotativo em cookies HttpOnly na mesma origem; OIDC Google/Apple como *login social*.
- **Consequências**: nenhum token acessível a JS (mitiga XSS → roubo de sessão); sem dependência de Keycloak/Auth0 no arranque.
- **Rejeitadas**: tokens em `localStorage`; Keycloak (operacionalmente pesado para um produto B2C pequeno — reavaliar para SSO empresarial);
  Spring Authorization Server (útil só quando houver clientes OAuth de terceiros).

## ADR-013 — Componentes de calendário próprios em vez de FullCalendar
- **Contexto**: o EscalasPT usa FullCalendar; o Turnos precisa de modo pincel, roster pessoas × dias e chips muito compactos em mobile.
- **Decisão**: `MonthGrid`, `TimeGrid`, `RosterGrid` próprios sobre `date-fns`/`@date-fns/tz` + `@dnd-kit`.
- **Consequências**: controlo total de UX/acessibilidade e bundle menor; custo inicial de desenvolvimento (~2 semanas) compensado pela centralidade do componente no produto.
- **Rejeitadas**: FullCalendar (vista *resource timeline* é paga; personalização profunda do *month view* é difícil); Schedule-X (reavaliar para `TimeGrid` se o custo apertar).

## ADR-014 — Dinheiro e horas como valores exatos
- **Decisão**: `BigDecimal` + `HALF_EVEN` no backend, `numeric` na BD, strings decimais no JSON; minutos inteiros para durações.
- **Rejeitadas**: `double`/`float` (erros de arredondamento acumulados em somas mensais).

## ADR-015 — Trocas GNR entre camaradas, sem autorização do comandante
- **Contexto**: o público é a GNR. No EscalasPT, uma troca aceite pelo camarada ficava presa à espera do comandante
  (`PENDING_APPROVAL`), e o documento só existia depois disso.
- **Decisão**: a troca é um acordo entre os dois militares da mesma escala. O camarada **aceita**, **pede para aguardar** ou **recusa**.
  Na aceitação, os serviços trocam de dono e o formulário oficial "Troca de Serviço" é emitido na mesma transação.
  O prazo do Art. 34.º, n.º 2 ("até à véspera da execução") passa a ser uma regra do sistema: expiração automática na véspera.
- **Consequências**: o `decide_swap`, o estado `PENDING_APPROVAL` e as notificações aos comandantes desaparecem.
  A prova da troca passa a ser o registo digital (cronologia, SHA-256 e código de verificação público). A caixa "VISTO"
  fica no modelo oficial, em branco, sem bloquear nada.
- **Rejeitadas**: manter um aprovador opcional por escala (reintroduz o comandante por outra porta); emitir o PDF de forma
  assíncrona depois da aceitação (poderia haver trocas aceites sem documento).
- Especificação: [doc 09](09-trocas-gnr.md). Substitui, para as escalas GNR, a política `ADMIN_APPROVAL` do ADR-011.
