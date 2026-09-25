# Turnos — Design & Arquitetura

> **Turnos** (nome de trabalho) é a evolução do EscalasPT para uma **aplicação de calendário de turnos** genérica:
> backend em **Java (Spring Boot)** e frontend em **Next.js (React)**, sem a hierarquia de postos/comandos
> e sem os papéis militares (comandante, adjunto, secretaria, militar).

Este diretório contém o desenho completo do produto e da arquitetura, pronto para arrancar a implementação.

| # | Documento | Conteúdo |
|---|-----------|----------|
| 1 | [Visão de produto](01-visao-produto.md) | Problema, personas, funcionalidades, âmbito do MVP, o que sai/entra face ao EscalasPT |
| 2 | [Arquitetura](02-arquitetura.md) | Visão C4, monólito modular, stack, módulos, fluxos, tempo real, jobs, escalabilidade |
| 3 | [Modelo de dados](03-modelo-de-dados.md) | ERD, DDL PostgreSQL, modelação de tempo/fusos, rotações, restrições na BD |
| 4 | [API](04-api.md) | Convenções REST, endpoints, erros RFC 9457, eventos em tempo real, feed ICS |
| 5 | [Frontend & design](05-frontend-e-design.md) | Estrutura Next.js, estado, ecrãs, wireframes, design system, acessibilidade, PWA |
| 6 | [Segurança & operações](06-seguranca-e-operacoes.md) | Autenticação, autorização, privacidade/RGPD, observabilidade, CI/CD, deploy |
| 7 | [Decisões (ADRs)](07-decisoes-adr.md) | Registo das decisões de arquitetura e alternativas rejeitadas |
| 8 | [Roadmap](08-roadmap.md) | Fases, marcos, estrutura do repositório e plano de migração a partir do EscalasPT |

## Resumo em 60 segundos

- **Produto**: calendário pessoal de turnos (tipo SuperShift), *personal-first*, com **grupos opcionais**
  para partilhar calendários e **trocar turnos entre colegas** (peer-to-peer, aprovação por admin do grupo apenas se o grupo o exigir).
- **Diferenciadores**: modo "pincel" (pintar dias com um tipo de turno), **rotações** (ex.: `M M T T N N F F F F`),
  múltiplos calendários por utilizador, feriados PT (nacionais + municipais), contagem de horas/extra/remuneração,
  saldos de férias, lembretes push, **subscrição ICS** (Google/Apple Calendar), PWA offline.
- **Backend**: Java 25 LTS + Spring Boot 4 + Spring Modulith (monólito modular), PostgreSQL 18, Flyway,
  virtual threads, Redis (rate limiting + pub/sub), OpenAPI 3.1.
- **Frontend**: Next.js 16 (App Router) + TypeScript, TanStack Query, Tailwind CSS v4 + shadcn/ui (Radix),
  cliente de API **gerado a partir do OpenAPI**, next-intl (pt-PT/en), Serwist (PWA).
- **Qualidade**: invariantes críticos garantidos **na própria BD** (ex.: sobreposição de turnos com `EXCLUDE USING gist`),
  tempo modelado de forma segura para mudanças de hora (DST), outbox transacional para notificações fiáveis,
  Testcontainers + Playwright.

## Pressupostos assumidos (a validar)

1. "Sem postos e comandantes" ⇒ **não existe** uma entidade organizacional hierárquica nem um papel de chefia que
   cria e publica escalas para terceiros. Cada pessoa é dona do seu calendário.
2. A colaboração faz-se por **grupos** (equipa, família, colegas de serviço). Um grupo pode ter *admins*, mas apenas
   para gerir membros e, opcionalmente, aprovar trocas — não para "publicar escalas".
3. Se no futuro for preciso um modo "gestor de equipa" (alguém que planeia turnos para outros), o modelo suporta-o
   através de **partilha de calendário com permissão de edição**, sem reintroduzir a hierarquia (ver ADR-011).
