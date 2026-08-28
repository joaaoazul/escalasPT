# Caderno de Serviço — plano de execução

> **Versão 2** — revista contra o código do `escalasPT` (commit `556e3f9`).
> A v1 excluía o registo de pessoas identificadas. Esta versão **inclui-o**, como
> módulo desenhado de raiz com as salvaguardas próprias: ver
> [`MODULO-IDENTIFICACOES.md`](./MODULO-IDENTIFICACOES.md).

---

## 0. O que mudou face à v1

| # | Mudança | Porquê |
|---|---|---|
| 1 | **Módulo de identificações entra no plano** (§9 + documento próprio) | Decisão do João. Deixa de ser "fase 5 condicional vaga" e passa a design completo, com portão de activação explícito. |
| 2 | Nova correcção ao `escalasPT`: **`Permissions-Policy` e CSP** | O `SecurityHeadersMiddleware` do `escalasPT` envia `camera=(), geolocation=()`. Copiado tal e qual, **a câmara e o GPS não funcionam** — e são metade da app. Ver §1.3. |
| 3 | Todas as afirmações sobre o `escalasPT` foram verificadas no código | Ficheiro e linha em §1.2 e §1.3. As sete estavam certas. |
| 4 | Fase 5 passa a ter sub-fases com prova de feito | Um módulo com dados de pessoas não se entrega num salto. |

---

## 1. Repositório e stack

Repo novo em `C:\Users\joaoa\caderno`, a copiar a arquitectura do `escalasPT`
(que fica intocado). Mesmas versões, porque estão provadas em produção.

**Backend** — FastAPI 0.115, SQLAlchemy 2.0 async, asyncpg, Alembic, Postgres 16,
Redis 7 (rate limiting), PyJWT, passlib/bcrypt, pyotp, slowapi,
python-json-logger, cryptography, WeasyPrint, pytest + httpx.

**Frontend** — React 19, Vite 6, TS 5.7, TanStack Query v5, Zustand,
react-router 7, lucide-react, sonner, vite-plugin-pwa, Chart.js.
**CSS puro com custom properties**, como no `escalasPT`.
Novo: **Dexie** (IndexedDB) e **MapLibre GL + PMTiles**.

**Estrutura a espelhar**:
`backend/app/{config,database,dependencies,exceptions,middleware,main}.py` +
`models/ schemas/ routers/ services/ utils/`;
`frontend/src/{api,store,providers,hooks,layouts,components,features,pages,types,utils}`.

### 1.1 O que se copia tal e qual

| Peça | Ficheiro no `escalasPT` |
|---|---|
| `create_app()` + `lifespan` + ordem dos middlewares | `backend/app/main.py:27-148` |
| `Settings` + validadores que matam o arranque com segredo default | `backend/app/config.py` |
| Hierarquia `AppException` + `register_exception_handlers` | `backend/app/exceptions.py` |
| Logging JSON com redacção de `password|token|secret|…` | `backend/app/utils/logging.py` |
| Auth: rotação de refresh token, detecção de reutilização (revoga a família), lockout, sessões em `active_sessions`, TOTP cifrado | `backend/app/services/auth_service.py`, `backend/app/utils/security.py` |
| `get_current_user` que valida o `sid` contra `active_sessions` | `backend/app/dependencies.py:91-146` |
| Tarefa de limpeza de tokens/sessões no `lifespan` | `backend/app/main.py:47-86` |
| Cliente axios com refresh + `failedQueue`, token só em memória | `frontend/src/api/client.ts` |
| `Button` / `Input` / `Modal` (focus trap, Escape, devolve foco) | `frontend/src/components/ui/` |
| Tokens e classes globais do design system | `frontend/src/index.css:1-120` |
| `Dockerfile` multi-stage, user não-root, healthchecks, limites de memória/CPU | `backend/Dockerfile`, `docker-compose.yml` |
| `deploy/setup.sh`: gera segredos com `openssl rand` + `Fernet.generate_key()` | `deploy/setup.sh` |

### 1.2 O que se corrige (bugs verificados que não se replicam)

**1. A app liga-se com um role limitado.**
No `escalasPT`, `backend/scripts/init_db.sql` cria o role `gnr_app` e a migração
`001_initial.py:207-225` faz `REVOKE UPDATE, DELETE ON audit_logs FROM %I` sobre
ele — mas o `DATABASE_URL` usa `${POSTGRES_USER}` (`docker-compose.yml:57`,
`deploy/docker-compose.prod.yml:59`), que é o **dono das tabelas**. O dono ignora
o `REVOKE` e, por omissão, ignora RLS. Resultado: **o audit log não é imutável e
a RLS não se aplica ao role que a app realmente usa.**
→ No caderno: `DATABASE_URL` usa `caderno_app`; o dono só é usado pelo Alembic.
Teste que falha se isto regredir: `test_audit_log_is_append_only`.

**2. Setting vazio = negar, não permitir.**
`007_add_rls_policies.py:44-48` (e as outras quatro policies):
`current_setting('app.current_station_id', true) = '' OR station_id = …`.
Um `station_id` em falta ou inválido produz `SET LOCAL … = ''` → **bypass total**.
→ No caderno a policy é:
```sql
CREATE POLICY registos_equipa_isolation ON registos
USING (
    nullif(current_setting('app.current_equipa_id', true), '') IS NOT NULL
    AND equipa_id = current_setting('app.current_equipa_id')::uuid
);
```
Os trabalhos de fundo (limpeza, backups, conservação) usam uma sessão que **define
explicitamente** o contexto por equipa, ou corre com um role próprio
`caderno_jobs` com `BYPASSRLS` — nunca por omissão silenciosa.

**3. Migrações idempotentes e sem nomes de role hardcoded.**
`001_initial.py` cria policies que a `007` volta a criar; a `007` declara
`APP_ROLE = "app_user"` — um role que não existe em lado nenhum (o real é
`gnr_app`/`escalaspt_app`). Daí os dois commits de correcção `1116b5c` e `57c7b2b`.
→ No caderno: `DROP POLICY IF EXISTS` antes de cada `CREATE POLICY`, e o role
resolve-se sempre em bloco `DO $$ … format('%I', role)`, como em `001_initial.py:210-224`.

**4. Testes em base de dados dedicada.**
`backend/tests/conftest.py:31-45`: `TEST_DB_URL = settings.DATABASE_URL` seguido de
`Base.metadata.drop_all` — correr `pytest` com o `.env` de desenvolvimento **apaga a
base de dados de desenvolvimento**.
→ No caderno: `TEST_DATABASE_URL` obrigatório, com validador que rejeita um nome
que não termine em `_test`.

**5. CI a sério.**
Hoje só existe `.github/workflows/security.yml` (Bandit/pip-audit).
→ No caderno: job `pytest` com Postgres 16 e Redis 7 de serviço, `tsc -b`,
`npm run build`, `npm audit`, Bandit e pip-audit em cada push.

**6. Utilitários num só sítio.**
`.badge-*` está definido em `frontend/src/index.css:375-391` (`badge-green`,
`badge-amber`, …) e outra vez em `frontend/src/pages/AdminPages.css:113-117`
(`badge-success`, `badge-warning`, …), com valores diferentes — e a linha 113/114
troca `--color-primary-400` com `--color-info-400`.
→ No caderno: uma escala de badges, no `index.css`, com nomes semânticos.

**7. Ícones PWA em PNG 192/512 + maskable**, não um SVG único.

### 1.3 A correcção que decide se a app funciona

`backend/app/middleware.py:64-73`, `SecurityHeadersMiddleware`:

```python
response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self' wss:; …"
)
```

`camera=()` e `geolocation=()` significam **negado a toda a gente, incluindo à
própria origem**. Copiar este ficheiro tal e qual entrega uma app em que o botão
da câmara não abre nada e o GPS devolve `PERMISSION_DENIED` — e ninguém percebe
porquê, porque não há erro visível de rede. O `img-src` sem `blob:` também parte
as miniaturas locais das fotos ainda por sincronizar.

Cabeçalhos do caderno:

```python
response.headers["Permissions-Policy"] = (
    "camera=(self), geolocation=(self), microphone=(), payment=(), interest-cohort=()"
)
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; script-src 'self'; worker-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)
```

`worker-src blob:` é para o service worker e para os workers do MapLibre;
`connect-src 'self'` chega — a app não fala com a internet (§8).
**Teste de fumo da fase 0**: um teste que faz `GET /api/health` e afirma que
`Permissions-Policy` contém `camera=(self)`. É barato e apanha a regressão.

---

## 2. Modelo de dados

Tudo com `UUIDMixin` + `TimestampMixin` de `models/base.py`, **mas o id é gerado
no cliente** (UUIDv7) — é o que torna a sincronização idempotente (§4). O
`default=uuid.uuid4` do mixin fica como rede de segurança para escritas do
servidor.

- **`users`** — `nome`, `nip`, `email`, `password_hash`, `role`
  (`agente` | `chefe_equipa` | `admin`), `equipa_id`, `is_active`, TOTP cifrado.
- **`equipas`** — unidade de isolamento (posto/secção/patrulha). Toda a RLS gira
  em torno de `equipa_id`.
- **`servicos`** — o turno: `inicio`, `fim`, `tipo` (patrulha, trânsito,
  investigação…), `viatura`, `acompanhantes` (M2M para `users`), `area`,
  `estado` (`aberto` | `fechado`), `autor_id`, `equipa_id`.
- **`registos`** — a entidade central, com discriminador `tipo`:
  `ocorrencia` | `fiscalizacao` | `nota`.
  `servico_id`, `autor_id`, `equipa_id`, `subtipo_id` (catálogo), `datahora`,
  `local_texto`, `lat`, `lon`, `freguesia`, `descricao` (cifrado), `resultado`
  (cifrado), `referencia_oficial` (nº de auto/NUIPC — texto), `contagens`
  (JSONB: veículos fiscalizados, testes de álcool, …), `estado`
  (`rascunho` | `fechado`), `conservar_ate` (date), `anonimizado_em`.
- **`anexos`** — `registo_id`, `finalidade`
  (`local` | `viatura` | `dano` | `objecto` | `documento_proprio`),
  `mime`, `bytes`, `sha256`, `caminho`, `thumb_caminho`, `autor_id`.
  Ficheiros **cifrados em disco** (§6), servidos só pela API.
- **`catalogos`** — tipos e subtipos configuráveis pelo João, sem deploy.
- **`modelos_texto`** — modelos de auto/relatório com marcadores (§7).
- **`audit_logs`** — como no `escalasPT` (`user_id`, `action`, `resource_type`,
  `resource_id`, `old_data`/`new_data` JSONB, `ip`, `user_agent`), append-only
  **a sério** (§1.2 nº 1), com `create_audit_log()` a sanitizar chaves sensíveis.
- **`refresh_tokens`**, **`active_sessions`** — copiados.

Tabelas do módulo de identificações (`pessoas`, `veiculos`,
`registo_intervenientes`, `registo_veiculos`, `ident_activacoes`,
`ident_consultas`) em [`MODULO-IDENTIFICACOES.md`](./MODULO-IDENTIFICACOES.md) §3.
**Existem no esquema desde a fase 1** (para não haver migração dolorosa depois),
mas ficam vazias e inacessíveis até o portão da §9 estar fechado.

**RLS** em `servicos`, `registos`, `anexos`, `catalogos`, `modelos_texto` e em todas
as tabelas de identificação: isolamento por `equipa_id` via
`SET LOCAL app.current_equipa_id`, com `ENABLE` + `FORCE ROW LEVEL SECURITY` e a
policy da §1.2 nº 2. O `agente` só vê e edita o que é seu; o `chefe_equipa` vê a
equipa; o `admin` administra mas **não é excepção à auditoria**.

---

## 3. Ecrãs

Desenho móvel primeiro (é onde se usa), denso no desktop.

- **`/`** — o dia: serviço aberto no topo com cronómetro, botão grande
  **"+ Registo"**, lista do que já foi registado hoje, indicador de sincronização
  (quantos por enviar).
- **Folha de registo** — bottom sheet, um ecrã, sem navegação: tipo (chips) →
  hora (pré-preenchida) → local (GPS com um toque, editável) → descrição →
  fotos (câmara directa) → resultado/referência. Guarda-se em ~20 segundos.
- **`/servicos`** — histórico de turnos; abrir um mostra tudo o que lá dentro
  aconteceu e o botão de PDF.
- **`/registos`** — lista com pesquisa em texto livre, filtros por tipo, data,
  local. Tabela larga no desktop, cartões no telemóvel.
- **`/painel`** — KPIs, gráficos e mapa (§8).
- **`/redaccao/:id`** — texto gerado, editável, botão copiar (§7).
- **`/admin`** — utilizadores, catálogos, modelos de texto, auditoria, idade da
  última cópia de segurança boa, e a **fila de conservação**: registos que
  passaram do prazo, para o João decidir (avisar, não apagar sozinho).

Design: tokens do `escalasPT` (`index.css`), tema escuro,
`--color-primary-500` esmeralda. Alvos de toque ≥ 44 px, uso a uma mão, botão de
registo alcançável com o polegar.

---

## 4. Offline-first (a parte difícil)

**Padrão outbox com ids gerados no cliente.**

1. Toda a escrita cria um **UUIDv7 no telemóvel** e grava primeiro no **Dexie**
   (`servicos`, `registos`, `anexos`, `outbox`). O ecrã actualiza imediatamente —
   nunca há um estado "a guardar".
2. A operação entra na tabela `outbox`
   (`{id, metodo, url, payload, tentativas, proxima_tentativa, erro}`).
3. Um *drainer* (`src/sync/outbox.ts`) esvazia a fila quando `navigator.onLine`,
   **em série**, com backoff exponencial e limite de tentativas. Acordado por:
   arranque da app, evento `online`, `visibilitychange` e **Background Sync** do
   service worker quando o browser o permite.
4. O servidor aceita o id do cliente como chave primária. `POST` de um id que já
   existe devolve **200 com o registo existente** em vez de 409 — a retentativa é
   inofensiva por construção. Sem remapeamento de ids depois de sincronizar.
5. **Fotos**: o blob fica no Dexie; o upload é uma entrada de outbox própria,
   posterior à do registo. Enquanto não sobe, a UI mostra a miniatura local. Cada
   anexo leva o `sha256` para se detectar duplicado.
6. **Conflitos**: um registo tem um único autor e só é editável por ele enquanto
   está em `rascunho`; o servidor recusa alterações a registos `fechado`. Com esta
   regra os conflitos deixam de existir na prática — e é por isso que ela existe,
   em vez de um resolvedor de merge que ninguém consegue testar.
7. **Leitura offline**: `persistQueryClient` do TanStack Query com persister em
   IndexedDB, para o histórico recente estar lá sem rede.
8. **O que nunca fica em cache local**: dados de pessoas. Escrevem-se no Dexie só
   enquanto estão pendentes e são apagados assim que o servidor confirma
   (`MODULO-IDENTIFICACOES.md` §6). O telemóvel não é um ficheiro de pessoas.

**Nota que decide o deploy:** service worker, câmara e geolocalização exigem
**contexto seguro**. `http://100.x.x.x` não é contexto seguro — a app não
funcionaria. Daí o §5. E os cabeçalhos da §1.3, sem os quais o contexto seguro
também não chega.

---

## 5. Deploy (VPS existente, só na tailnet)

`docker compose` com `postgres`, `redis`, `api`, `nginx`, em rede própria
`caderno-net`, no mesmo VPS do MAIA mas sem lhe tocar (nomes de contentor,
volumes, rede e porta distintos).

**Exposição**: o nginx **não** publica em `0.0.0.0`. Publica em `127.0.0.1:8090`
e o acesso faz-se por **`tailscale serve --bg 8090`**, que termina TLS com o
certificado `*.ts.net` da máquina. Resultado:
`https://<maquina>.<tailnet>.ts.net` — certificado válido, contexto seguro, PWA
instalável, câmara a funcionar, e **zero superfície pública**. Sem registo DNS,
sem porta aberta, sem Funnel.

`deploy/setup.sh` no mesmo molde do `escalasPT`: gera segredos com `openssl rand`
e `Fernet.generate_key()`, valida que não sobrou nenhum `GENERATE_ME`, sobe,
espera pelo healthcheck e corre as migrações. Segredos a gerar:
`JWT_SECRET`, `POSTGRES_PASSWORD`, `CADERNO_APP_DB_PASSWORD`, `REDIS_PASSWORD`,
`TOTP_ENCRYPTION_KEY`, `ATTACHMENT_MASTER_KEY`, `FIELD_ENCRYPTION_KEY`,
`IDENT_FIELD_KEY`, `IDENT_INDEX_KEY` (§9).

**Ordem das migrações** (aprendida no MAIA, e vale aqui):
`build` → `docker compose run --rm --no-deps api alembic upgrade head` →
`up -d --wait`. Nunca `up -d` antes da migração.

> ⚠️ O classificador de permissões bloqueia `docker compose up -d` e
> `alembic upgrade`. Esses passos corre-os o João, com `! ssh …` no prompt — aviso
> antes de começar o deploy, para não ficarmos a meio.

---

## 6. Segurança e conservação

- **Anexos cifrados em disco**: AES-GCM com chave por ficheiro, embrulhada por uma
  chave-mestra em `ATTACHMENT_MASTER_KEY`. Nunca servidos como estáticos — passam
  sempre por `GET /api/anexos/{id}/conteudo`, que autoriza e **regista o acesso na
  auditoria**.
- **Campos de texto livre** (`descricao`, `resultado`) cifrados ao nível da
  aplicação com um `TypeDecorator` do SQLAlchemy — um dump da base de dados não é
  legível. (O `escalasPT` cifra à mão no service; aqui fica transparente e não há
  como esquecer.) Consequência assumida: não há `LIKE` no servidor sobre estes
  campos — a pesquisa em texto livre da §3 é feita no cliente sobre o que está em
  cache, ou por metadados (tipo, data, local, freguesia).
- **Auditoria** de tudo o que lê ou exporta: abrir anexo, gerar texto, gerar PDF,
  exportar estatística, consultar ficha. Append-only garantido pelo `REVOKE` — que
  desta vez funciona, porque a app liga com role limitado (§1.2 nº 1).
- **Conservação**: cada registo nasce com `conservar_ate` conforme o tipo
  (configurável em `/admin`). Passado o prazo entra na **fila de revisão** e a app
  avisa; **nada é apagado sem o João carregar no botão**. Ao apagar, os campos
  descritivos e os anexos vão-se e fica a linha estatística anónima (tipo, data,
  zona), para os gráficos não perderem histórico.
- **Backups**: `pg_dump` cifrado + anexos, com trabalho diário e verificação de que
  correu. No MAIA os backups estiveram 7 dias parados sem ninguém dar por isso —
  aqui o painel de admin mostra a **idade da última cópia boa**, e o healthcheck
  fica amarelo acima de 48 h. As chaves de cifra **não** vão no mesmo destino do
  backup.
- **Bloqueio do dispositivo**: PIN da app (≥ 6 dígitos) que fecha a sessão local e
  limpa a cache sensível ao fim de N minutos em segundo plano. Sem isto, "o
  telemóvel na mesa" é o modelo de ameaça real.

---

## 7. Redacção

Modelos por subtipo, guardados em `modelos_texto`, com marcadores
(`{{datahora}}`, `{{local}}`, `{{descricao}}`, `{{referencia_oficial}}`…) e
editáveis pelo João sem deploy. `POST /api/registos/{id}/texto` devolve o texto
composto; o ecrã mostra-o editável com botão **copiar**.

**Determinístico, sem LLM nesta fase** — de propósito: o modelo local escreve a
~11 tokens/s e serve um pedido de cada vez, portanto uma geração no telemóvel a
meio de um turno seria pior do que escrever à mão. Se mais tarde valer a pena,
entra como botão opcional de "melhorar redacção", nunca no caminho crítico — e
nunca com dados de pessoas no prompt.

**PDF do turno**: WeasyPrint no backend, com cabeçalho do serviço, registos por
ordem cronológica e miniaturas dos anexos. Geração auditada.

---

## 8. Painel e mapa

Gráficos com Chart.js (já usado no `escalasPT`): registos por tipo, por hora do
dia, por dia da semana, evolução mensal, e o topo de locais.

**Mapa auto-alojado, sem serviços externos** (a app não fala com a internet):
MapLibre GL + um extracto **PMTiles** da área de interesse (Algarve ≈ 100 MB),
servido pelo próprio nginx com pedidos por intervalo (`Accept-Ranges`). Camada de
pontos quentes por densidade de registos. O mesmo ficheiro serve o modo offline —
a região fica em cache no telemóvel.

Os pontos do mapa são de **registos**, nunca de pessoas: não há, e não haverá,
mapa de moradas ou de paradeiros.

---

## 9. Módulo de identificações

Desenho completo em [`MODULO-IDENTIFICACOES.md`](./MODULO-IDENTIFICACOES.md).
Resumo do que decide a arquitectura:

1. **Desligado por omissão.** O código existe, as tabelas existem, mas a API
   devolve 403 enquanto não houver um registo de activação
   (`ident_activacoes`) com finalidade, base legal, responsável pelo tratamento,
   prazos e referência da autorização. Ligar o módulo é um acto documentado, não
   uma checkbox.
2. **O responsável pelo tratamento é a GNR, não o João.** Um ficheiro de pessoas
   identificadas em serviço é tratamento de dados por autoridade competente para
   fins penais — Lei 59/2019 (Directiva (UE) 2016/680) — ou RGPD/Lei 58/2019 na
   parte contra-ordenacional. Antes de ligar: parecer do EPD da GNR, inscrição no
   registo de actividades de tratamento e, por haver categorias especiais e
   tecnologia nova, avaliação de impacto. **Isto não bloqueia construir; bloqueia
   ligar** — e a app é que faz cumprir o bloqueio.
3. **Minimização a sério**: nome, data de nascimento, tipo e número de documento,
   papel no registo, referência do auto. Nada de saúde, religião, origem ou
   opinião. **Biometria e reconhecimento facial: proibidos por desenho** — a app
   nunca processa uma imagem além de lhe fazer miniatura.
4. **Sem navegação exploratória**: não há listagem de pessoas nem `LIKE` sobre
   nomes. Chega-se a uma ficha a partir de um registo próprio, ou por pesquisa de
   **correspondência exacta** sobre um índice HMAC (documento, matrícula, nome
   completo normalizado), sempre com **motivo obrigatório** e sempre auditada.
5. **Cifra dedicada**: campos identificativos com chave própria
   (`IDENT_FIELD_KEY`), índices de pesquisa com HMAC de chave separada
   (`IDENT_INDEX_KEY`). Comprometer o dump não chega para ler, e a chave de
   índice não abre os dados.
6. **Prazos curtos e revistos**: 90 dias sem auto associado, 1 ano com auto
   (configuráveis). No fim, anonimização — fica a linha estatística, desaparece a
   pessoa.
7. **Nada disto vive no telemóvel** (§4 nº 8).

---

## 10. Fases

| Fase | Conteúdo | Prova de que está feito |
|---|---|---|
| **0** | Repo, docker, migração inicial, auth, design system, cabeçalhos da §1.3, deploy na tailnet | Entrar pelo telemóvel em `https://…ts.net`, instalar a PWA, e a câmara abrir |
| **1** | Serviços + registos + fotos + outbox offline | Registar em modo avião, ligar a rede, ver subir sozinho — uma só vez |
| **2** | Redacção + PDF do turno | Copiar o texto de um registo e gerar o PDF do turno |
| **3** | Painel + mapa | Gráficos e pontos quentes com dados reais, sem um pedido para fora |
| **4** | Admin: catálogos, modelos, utilizadores, auditoria, fila de conservação, idade do backup | Apagar um registo expirado e ver ficar só a linha anónima |
| **5.0** | **Portão** do módulo de identificações: finalidade, base legal, responsável, prazos, autorização | `ident_activacoes` preenchido; sem ele, 403 em todas as rotas do módulo |
| **5.1** | Modelo, cifra, índices HMAC, RLS e auditoria das identificações (sem UI) | Testes: outra equipa recebe 404; setting vazio nega; consulta fica auditada |
| **5.2** | Intervenientes a partir do registo (sem pesquisa, sem ficha) | Associar pessoa/veículo a uma fiscalização e gerar o auto com os campos certos |
| **5.3** | Ficha de pessoa + pesquisa por correspondência exacta com motivo | Encontrar por nº de documento; ver no log quem consultou, quando e porquê |
| **5.4** | Conservação, anonimização e dossier do titular | Expirar uma ficha e ver ficar só a estatística; exportar o dossier de um titular |
| **5.5** | *(decisão à parte)* Fotografia de pessoa/documento de terceiro | Só avança com fundamento escrito na activação |

As fases 0–4 não dependem de nenhuma decisão do módulo 5. Se o portão nunca
fechar, a app continua completa e útil — que é a razão de o desenho ser este.

---

## 11. Verificação

**Backend** — `cd backend && pytest`, contra `caderno_test`:
- auth: rotação e detecção de reutilização de refresh token, lockout, revogação
  de sessão;
- **idempotência**: o mesmo `POST` duas vezes dá um registo e 200 à segunda;
- **RLS**: utilizador de outra equipa recebe 404, e um setting vazio **nega** em
  vez de permitir (o teste que o `escalasPT` não tem);
- **audit log append-only**: `UPDATE`/`DELETE` como `caderno_app` levam
  `InsufficientPrivilege`;
- **cabeçalhos**: `Permissions-Policy` traz `camera=(self)` e `geolocation=(self)`;
- conservação: expirar → fila → anonimizar deixa a linha estatística e apaga os
  anexos do disco;
- identificações: portão fechado ⇒ 403; consulta sem motivo ⇒ 422; toda a consulta
  deixa linha em `ident_consultas`; limite de consultas por hora.

**Frontend** — `npm run build` (corre `tsc -b`) e Vitest ao drainer do outbox:
fila com falhas de rede intermitentes tem de convergir sem duplicar; blob de foto
sobrevive a recarregar a página; dados de pessoa desaparecem do Dexie depois do
`ack`.

**Ponta a ponta, no telemóvel** (é o único teste que conta): modo avião → dois
registos com fotos → ligar → confirmar que subiram uma só vez, com as fotos
certas, e que o PDF do turno os mostra.

**CI** — pytest + `npm run build` + Bandit + pip-audit + `npm audit` em cada push.

---

## 12. Riscos e decisões em aberto

| Risco | Mitigação |
|---|---|
| O portão da fase 5 nunca fecha (autorização institucional demora ou não vem) | As fases 0–4 são autónomas e entregam a app completa. O módulo fica dormente, não meio-feito. |
| Telemóvel perdido com registos por sincronizar | PIN da app, limpeza automática da cache, sem dados de pessoas em local, e `tailscale device revoke` corta o acesso à API. |
| Cifra de campo impede pesquisa no servidor | Assumido: pesquisa por metadados no servidor, texto livre no cliente. Se um dia doer, entra um índice HMAC de palavras — não texto em claro. |
| PMTiles de 100 MB no telemóvel | Só a região à volta é que fica em cache; o ficheiro completo é servido pelo nginx sob pedido por intervalo. |
| Deriva face ao `escalasPT` (correcções que lá continuam por fazer) | As sete correcções da §1.2 estão descritas com ficheiro e linha; se valer a pena, entram no `escalasPT` como PR próprio. |
