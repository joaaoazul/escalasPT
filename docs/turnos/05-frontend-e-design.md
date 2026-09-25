# 5. Frontend & design

## 5.1 Porquê Next.js (e como o usar sem complicar)

A app é, na sua maioria, uma **SPA autenticada muito interativa**. O Next.js justifica-se por:

- **Uma só base de código** para landing page (SEO, marketing, páginas legais) e aplicação.
- **Layouts aninhados** do App Router (shell com navegação que não re-renderiza entre páginas).
- **Primeiro *paint* com dados**: a página do calendário faz *prefetch* no servidor (RSC) e hidrata o cache do TanStack Query,
  evitando o *spinner* inicial.
- Rotas i18n (`/pt`, `/en`) e *middleware* para redirecionar não-autenticados.

Regras para não criar um segundo backend:
1. **Server Components** só para *layout* e *prefetch*; tudo o que é interativo é Client Component.
2. **Nada de Server Actions com lógica de negócio** — mutações vão diretamente à API Java (mesma origem, cookie).
3. O Next.js nunca fala com a BD.
4. `output: 'standalone'` → imagem Docker pequena com `node server.js`.

## 5.2 Rotas

```
src/app/
├── [locale]/
│   ├── (marketing)/                 # público, estático
│   │   ├── page.tsx                 # landing
│   │   ├── privacidade/ · termos/
│   ├── (auth)/                      # layout centrado, sem navegação
│   │   ├── entrar/  registar/  recuperar/  verificar-email/
│   │   └── convite/[token]/         # pré-visualização de convite de grupo
│   └── (app)/                       # layout com shell: sidebar (desktop) / tab bar (mobile)
│       ├── layout.tsx               # verifica sessão (middleware) + SSE provider + prefetch /me, /calendars
│       ├── hoje/                    # "Hoje": próximo turno, contagem decrescente, quem está de serviço nos grupos
│       ├── calendario/              # ?cal=<id>&vista=mes|semana|dia|agenda|ano&data=2026-10
│       ├── estatisticas/            # horas, dinheiro, saldos
│       ├── grupos/
│       │   ├── page.tsx
│       │   └── [groupId]/
│       │       ├── page.tsx         # roster
│       │       ├── trocas/  membros/  atividade/  definicoes/
│       ├── trocas/                  # caixa de entrada de trocas (todos os grupos)
│       ├── notificacoes/
│       └── definicoes/
│           ├── perfil/  seguranca/  notificacoes/  dados/      # conta
│           └── calendarios/[calId]/{geral,tipos,rotacoes,remuneracao,ausencias,partilha,feriados}
└── api/                             # NÃO usado para negócio (apenas /api/health do Next)
```

## 5.3 Organização do código

```
src/
├── app/                      # rotas (finas: compõem features)
├── features/                 # cada feature = UI + hooks + lógica cliente
│   ├── calendar/
│   │   ├── components/       # MonthGrid, DayCell, ShiftChip, TimeGrid, AgendaList, YearHeatmap, PaintToolbar
│   │   ├── hooks/            # useShifts(calId, range), usePaint(), useUndoRedo()
│   │   ├── lib/              # date math (grid do mês, segmentação visual de turnos noturnos)
│   │   └── index.ts          # API pública da feature
│   ├── shift-types/  rotations/  stats/  groups/  swaps/  notifications/  settings/  auth/
├── components/
│   ├── ui/                   # shadcn/ui gerado + nossos primitivos (Button, Sheet, Dialog, Command…)
│   └── layout/               # AppShell, Sidebar, BottomTabs, PageHeader
├── lib/
│   ├── api/
│   │   ├── schema.d.ts       # GERADO (openapi-typescript)
│   │   ├── client.ts         # openapi-fetch + middleware (X-Requested-With, refresh em 401, Problem Details → ApiError)
│   │   └── query-keys.ts     # fábrica de query keys
│   ├── sse.ts                # EventSource + reconexão + mapa evento → invalidação
│   ├── time.ts               # wrappers date-fns + @date-fns/tz (fuso do calendário, não do browser!)
│   └── color.ts              # contraste automático de texto sobre cor do turno
├── messages/{pt-PT,en}.json  # next-intl
└── styles/globals.css        # tokens + Tailwind v4 @theme
```

Regra de importação (ESLint `no-restricted-imports`): `features/x` não importa internos de `features/y`, só o `index.ts`.
O mesmo espírito dos módulos do backend.

## 5.4 Estado e dados

| Tipo de estado | Onde vive | Exemplo |
|----------------|-----------|---------|
| Dados do servidor | **TanStack Query** | turnos, tipos, grupos, trocas |
| Estado navegável | **URL** (`nuqs`) | calendário ativo, vista, mês, filtros |
| Estado de interação efémero | `useState` / **Zustand** (pequeno store por feature) | tipo selecionado no pincel, pilha desfazer/refazer, seleção múltipla |
| Preferências locais | `localStorage` (com *try/catch*) | tema, último calendário aberto |

**Query keys**

```ts
export const qk = {
  me: ['me'] as const,
  calendars: ['calendars'] as const,
  shifts: (calId: string, from: string, to: string) => ['shifts', calId, from, to] as const,
  shiftTypes: (calId: string) => ['shift-types', calId] as const,
  roster: (gid: string, from: string, to: string) => ['roster', gid, from, to] as const,
  swaps: (scope: 'mine' | string) => ['swaps', scope] as const,
  stats: (calId: string, from: string, to: string) => ['stats', calId, from, to] as const,
};
```

**Optimistic update no pincel** (o momento mais importante de UX):

1. Toque num dia → `setQueryData(['shifts', cal, mês])` com turno "fantasma" (`id: tmp-…`, estado `pending`) — resposta visual < 16 ms.
2. Os toques acumulam-se num *buffer* e são enviados num único `PUT days:paint` após 400 ms sem toques (debounce) ou ao sair do modo pincel.
3. Sucesso → substituir pelos turnos reais; avisos → *badge* amarelo no dia + toast agregado.
4. Erro `422` → reverter os dias rejeitados, sacudir (animação curta) e mostrar o motivo no dia.
5. Cada lote vai para a pilha de desfazer (o inverso é um `shifts:batch`).

**Pré-carregamento**: ao ver outubro, faz-se *prefetch* de setembro e novembro (navegar entre meses é instantâneo).

## 5.5 Ecrãs principais (wireframes)

### Mobile — Calendário mensal (vista principal)

```
┌──────────────────────────────────┐
│ ☰  Hospital ▾          🔔2   (A) │  ← seletor de calendário, notificações, avatar
│ ‹  Outubro 2026  ›      Hoje     │
├──────────────────────────────────┤
│ Seg  Ter  Qua  Qui  Sex  Sáb  Dom│
│                  1    2    3    4│
│                 [M]  [M]  [T]  [T]│  ← chips coloridos com abreviatura
│  5🎉  6    7    8    9   10   11 │  ← 🎉 = feriado
│ [N]  [N]  [F]  [F]  [F]  [F]  [M]│
│ 12   13   14   15   16   17   18 │
│ [M]  [T]  [T]  [N]  [N]  [F]• [F]│  ← • = nota do dia
│ …                                │
├──────────────────────────────────┤
│ 168 h · 12 N · 2 FDS   ▸ detalhe │  ← resumo do mês (toque → estatísticas)
├──────────────────────────────────┤
│        ( 🖌 Pintar )              │  ← FAB: entra no modo pincel
├──────────────────────────────────┤
│ 🏠Hoje  📅Calendário  👥Grupos  ⋯ │  ← tab bar
└──────────────────────────────────┘
```

### Mobile — Modo pincel

```
┌──────────────────────────────────┐
│ ✕ Modo pincel          ↶  ↷      │
│ … grelha do mês (toque = pinta; │
│   arrastar = pinta vários) …     │
├──────────────────────────────────┤
│ [M 07-15] [T 15-23] [N 23-07]    │  ← paleta de tipos (scroll horizontal)
│ [F] [FER] [BX] [⌫ Limpar]        │
└──────────────────────────────────┘
```

### Mobile — Detalhe de dia (bottom sheet)

```
┌──────────────────────────────────┐
│ ─────                            │
│ Sábado, 24 out · Mudança de hora │
│ ┌──────────────────────────────┐ │
│ │▌N  Noite   22:00 → 05:00 (+1)│ │  ← aviso contextual de DST
│ │   8 h · 7 h noturnas         │ │
│ └──────────────────────────────┘ │
│ ⏱ +1 h extra   📝 Nota           │
│ [ Editar ] [ Trocar… ] [ Apagar ]│
└──────────────────────────────────┘
```

### Desktop — Calendário

```
┌────────────┬──────────────────────────────────────────────┬──────────────┐
│ TURNOS     │ ‹ Outubro 2026 ›  Hoje   [Mês|Semana|Dia|Agenda] 🖌  │ Resumo       │
│            ├──────────────────────────────────────────────┤ 168 h        │
│ Hoje       │ Seg   Ter   Qua   Qui   Sex   Sáb   Dom      │ Noites 12    │
│ Calendário │ grelha grande: cada célula mostra chip com   │ FDS 2        │
│ Estatíst.  │ nome, horário, ícone, notas; drag & drop;    │ Extra 3 h    │
│ Grupos     │ seleção múltipla com Shift+clique;           │ ≈ 1 843 €    │
│ Trocas (2) │ menu de contexto (clique direito)            ├──────────────┤
│            │                                              │ Tipos        │
│ Calendários│                                              │ ▌M Manhã  8  │
│ ☑ Hospital │                                              │ ▌T Tarde  6  │
│ ☑ Clínica  │                                              │ ▌N Noite  6  │
│ ＋ Novo     │                                              │ ▌F Folga 10  │
└────────────┴──────────────────────────────────────────────┴──────────────┘
```

### Roster de grupo (pessoas × dias)

```
              Seg5  Ter6  Qua7  Qui8  Sex9  Sáb10 Dom11
Ana (eu)       M     M     T     T     N     N     F
Rui            F     F     M     M     T     T     N
Marta          ░     ░     ░     M     M     ░     ░     ← ░ = só disponibilidade partilhada (ocupado)
Sofia          FER   FER   FER   FER   FER   F     F
─────────────────────────────────────────────────────
A trabalhar    2     2     3     4     3     2     1     ← contagem por dia
```
- Clicar no turno de um colega → "Propor troca com o meu turno de…".
- Linha fixa (sticky) com o próprio utilizador; colunas fixas com nomes; scroll horizontal por semanas em mobile.

### Trocas

- **Caixa de entrada** com separadores: *Para mim* (precisa da minha resposta) · *Enviadas* · *Ofertas no grupo* · *Histórico*.
- Cartão de troca: dois turnos lado a lado ("Dás N sáb 24" ⇄ "Recebes M dom 25"), impacto (descanso, horas da semana),
  ações sempre visíveis (lição aprendida no EscalasPT: nada escondido atrás de *hover* no telemóvel).

### Assistente de rotação

1. Escolher modelo (biblioteca) ou "Personalizada".
2. Editor de ciclo: fila de "blocos" arrastáveis (`M M T T N N F F F F`), comprimento visível.
3. Intervalo + "hoje é o dia **3** do ciclo" (seletor visual).
4. **Pré-visualização** num mini-calendário com conflitos marcados → escolher SKIP/REPLACE.
5. Aplicar → toast com "Desfazer".

### Onboarding (primeiro minuto)

`Registo → fuso/concelho (pré-preenchido pelo browser) → "Como é o teu horário?" [Rotação fixa | Varia todos os meses | Horário fixo]
→ (rotação) assistente | (varia) modo pincel aberto no mês atual | (fixo) semana tipo → Calendário cheio.`

## 5.6 Design system

### Direção visual

O EscalasPT tinha uma estética "institucional escura" (verde militar). O Turnos é **pessoal e calmo**:
neutros quentes, uma cor de marca (índigo), e **as cores dos turnos são as protagonistas** — a UI recua para as deixar ler-se.

### Tokens

```css
@theme {
  /* Marca */
  --color-brand-500: oklch(0.58 0.19 270);   /* índigo */
  --color-brand-600: oklch(0.51 0.20 270);

  /* Superfícies (claro) */
  --color-bg:        oklch(0.99 0.003 90);
  --color-surface:   oklch(1 0 0);
  --color-surface-2: oklch(0.97 0.004 90);
  --color-border:    oklch(0.91 0.005 90);
  --color-fg:        oklch(0.22 0.01 270);
  --color-fg-muted:  oklch(0.50 0.01 270);

  /* Semântica */
  --color-success: oklch(0.63 0.15 150);
  --color-warning: oklch(0.75 0.15 75);
  --color-danger:  oklch(0.60 0.21 25);
  --color-holiday: oklch(0.65 0.18 20);

  /* Raio, sombra, tipografia */
  --radius-sm: 6px; --radius-md: 10px; --radius-lg: 16px;
  --font-sans: "Inter Variable", system-ui, sans-serif;
  --font-mono: "JetBrains Mono Variable", ui-monospace, monospace;   /* horas tabulares */
}
@media (prefers-color-scheme: dark) { /* e [data-theme="dark"] */ … }
```

- **Tema escuro e claro** de primeira classe, seguindo o sistema por omissão.
- Números (horas, contagens) com `font-variant-numeric: tabular-nums`.

### Paleta de turnos

- 16 cores pré-definidas escolhidas para serem **distinguíveis entre si** (incluindo daltonismo deuteranopia/protanopia) e
  com versões para claro/escuro.
- Cor livre permitida, mas o texto do *chip* é escolhido automaticamente (preto/branco) pelo **contraste APCA/WCAG ≥ 4.5:1**
  (`lib/color.ts`). Aviso no editor se duas cores do mesmo calendário forem demasiado parecidas (ΔE OKLab < 0.08).
- **A cor nunca é a única pista**: o *chip* mostra sempre a abreviatura; ausências têm padrão tracejado; feriados têm ícone.

### Componentes-chave (Storybook)

`ShiftChip` (tamanhos xs/sm/md, estados pending/warning/error/swap-pending) · `DayCell` · `MonthGrid` · `TimeGrid` · `RosterGrid` ·
`ShiftTypePicker` · `PaintToolbar` · `RotationEditor` · `SwapCard` · `StatTile` · `EmptyState` · `BottomSheet` · `CommandMenu (⌘K)`.

### Movimento

- Transições 150–200 ms, `ease-out`; mudança de mês desliza horizontalmente (gesto *swipe* em mobile).
- `prefers-reduced-motion` desliga animações não essenciais.

## 5.7 Acessibilidade (WCAG 2.2 AA)

- `MonthGrid` segue o padrão **ARIA grid**: setas movem o foco entre dias, `Enter` abre o dia, `Espaço` pinta no modo pincel,
  `PageUp/PageDown` muda de mês. Cada célula tem `aria-label` completo ("Sábado, 24 de outubro, Noite das 22:00 às 05:00, feriado").
- Alvos de toque ≥ 44×44 px (as células do mês em 360 px de largura têm ~48 px).
- Radix garante *focus trap* e retorno de foco em diálogos/sheets.
- Testes automáticos com **axe** (Playwright + Storybook a11y addon) no CI.

## 5.8 PWA e offline

- **Serwist**: *precache* do *shell*; `StaleWhileRevalidate` para `GET /calendars/*/shifts` (últimos 3 meses vistos);
  `NetworkOnly` para tudo o resto.
- Offline: calendário e "Hoje" continuam legíveis com banner "Sem ligação — a mostrar dados de há 2 h".
  Mutações offline ficam **desativadas** no MVP (evita conflitos de sincronização); v2 pode usar fila com `Idempotency-Key`.
- Manifest com `shortcuts` ("Pintar mês", "Hoje") e ícones *maskable*.
- **Web Push** com `sw.js` (mesma abordagem do EscalasPT, `sw-push.js`), ações na notificação ("Aceitar troca" abre direto o cartão).
- *Badging API* com o nº de trocas pendentes.

## 5.9 Desempenho

| Métrica | Alvo |
|---------|------|
| LCP (4G, móvel médio) | < 2.0 s |
| INP | < 150 ms (toque no modo pincel < 50 ms) |
| JS inicial da rota `/calendario` | < 150 kB gzip |

Técnicas: RSC para *shell*, `next/dynamic` para estatísticas/gráficos/editor de rotações, `React.memo` em `DayCell` com
*props* estáveis, virtualização (`@tanstack/react-virtual`) no roster com muitas pessoas e na agenda.

## 5.10 Testes do frontend

| Nível | Ferramenta | O quê |
|-------|------------|-------|
| Unitário | Vitest | `lib/time.ts` (grelha do mês, DST, semana a começar à segunda/domingo), `lib/color.ts`, reducers do pincel/undo |
| Componente | Vitest + Testing Library + MSW | `MonthGrid`, `PaintToolbar`, `SwapCard` com respostas da API simuladas a partir do OpenAPI |
| Visual | Storybook + Chromatic (ou Playwright screenshots) | Estados dos componentes em claro/escuro |
| E2E | **Playwright** contra stack real (docker compose) | O "fio condutor" do MVP (doc 01, §1.6) em Chromium + WebKit mobile |
