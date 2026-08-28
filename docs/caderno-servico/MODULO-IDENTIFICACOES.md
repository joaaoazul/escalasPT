# Módulo de identificações — pessoas e veículos

> Anexo ao [`PLANO.md`](./PLANO.md). Cobre o que a v1 do plano tinha deixado de
> fora: registar **quem** foi identificado, fiscalizado ou interveio numa
> ocorrência, e conseguir voltar lá.

O resto do caderno regista o **evento**. Este módulo regista as **pessoas e
veículos** que aparecem nesse evento. É a parte com mais valor prático no
terreno e é, ao mesmo tempo, a única do sistema em que um erro de desenho tem
consequências para terceiros. Daí ter documento próprio, portão de activação e
regras que a app faz cumprir sozinha — em vez de confiar em boas intenções.

---

## 1. Enquadramento (o que tem de estar resolvido antes de ligar)

Um ficheiro de pessoas identificadas em serviço não é uma nota pessoal: é
**tratamento de dados pessoais por autoridade competente**. O regime aplicável
depende da finalidade:

- **Lei 59/2019** (transpõe a Directiva (UE) 2016/680) — prevenção, detecção,
  investigação e repressão de infracções penais. É o regime da maior parte do que
  aqui se regista.
- **RGPD + Lei 58/2019** — o que for contra-ordenacional, administrativo ou de
  gestão interna.

Consequências que o desenho tem de reflectir, e reflecte:

| Exigência | Onde vive na app |
|---|---|
| **Responsável pelo tratamento** é a GNR, não o utilizador | `ident_activacoes.responsavel` — texto obrigatório, sem default |
| **Finalidade determinada, explícita e legítima** | `ident_activacoes.finalidade` + `base_legal`, obrigatórios |
| **Autorização institucional** (despacho/ordem de serviço) | `ident_activacoes.referencia_autorizacao` |
| **Parecer do EPD** e **registo da actividade de tratamento** | `ident_activacoes.parecer_epd` (referência + data) |
| **Avaliação de impacto** (novas tecnologias + dados sensíveis) | `ident_activacoes.aipd_referencia` |
| **Minimização** | Esquema fechado, §3 — não há campo "outros dados" |
| **Limitação da conservação** | `conservar_ate` por interveniente, §7 |
| **Segurança** | Cifra dedicada, RLS, 2FA, §5 |
| **Registo de acessos e consultas** (art. 55.º-56.º Lei 59/2019) | `ident_consultas` + `audit_logs`, §8 |
| **Direitos do titular** | Dossier e apagamento, §9 |

**Nada disto impede escrever o código.** O que impede é *ligar o módulo em
produção com dados reais* — e essa é uma decisão do João com o seu comando e o
EPD da GNR, não uma decisão técnica. A app existe para tornar essa fronteira
verificável: sem `ident_activacoes` válido, as rotas devolvem 403 e as tabelas
ficam vazias.

> **Uso pessoal vs institucional.** Se o módulo for usado como memória privada do
> próprio, fora de qualquer autorização, o utilizador fica sozinho como
> responsável pelo tratamento, com tudo o que isso implica. É por isso que o
> ecrã de activação obriga a escrever quem é o responsável: para que a resposta
> seja escrita por alguém, uma vez, em vez de assumida todos os dias.

---

## 2. Princípios de desenho (as regras que não se negoceiam)

1. **Desligado por omissão.** Fase 5.0 fecha o portão; até lá, 403.
2. **Sem navegação exploratória.** Não existe `GET /api/pessoas`. Não há listagem,
   não há paginação de pessoas, não há `LIKE '%…%'` sobre nomes. Só se chega a uma
   ficha por um caminho legítimo (§4).
3. **Sem biometria.** Nenhum processamento de rosto, impressão digital ou voz.
   Sem descritores, sem comparação de imagens, sem "pesquisar por foto". Se um dia
   isso for preciso, é o sistema oficial que o faz — não este.
4. **Motivo obrigatório em toda a consulta.** Curto, com sugestões, guardado.
   Uma consulta sem motivo é 422, não é um aviso.
5. **A app aponta para o auto, não o substitui.** `referencia_oficial` continua a
   ser o elo com o sistema oficial; este módulo é apoio ao trabalho do próprio, não
   um cadastro paralelo.
6. **Prazos curtos por omissão.** Guardar durante anos "por precaução" é
   exactamente o que a lei não permite.
7. **Nada em cache no telemóvel** (§6).
8. **O admin não é excepção.** Vê a auditoria; também é auditado.

---

## 3. Modelo de dados

Todas as tabelas com `UUIDMixin` + `TimestampMixin`, `equipa_id`, RLS por equipa
(policy da §1.2 nº 2 do `PLANO.md`), e criação no cliente proibida — **as pessoas
são sempre criadas com o servidor online**, ao contrário dos registos (§6).

### `pessoas`

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | uuid | PK |
| `equipa_id` | uuid | FK, RLS |
| `autor_id` | uuid | FK `users` — quem criou |
| `nome` | `EncryptedStr` | cifrado com `IDENT_FIELD_KEY` |
| `nome_idx` | bytea | HMAC-SHA256 do nome normalizado (§4) |
| `data_nascimento` | `EncryptedDate` | opcional |
| `tipo_documento` | enum | `cc`, `passaporte`, `titulo_residencia`, `carta_conducao`, `outro` |
| `numero_documento` | `EncryptedStr` | opcional |
| `documento_idx` | bytea | HMAC do documento normalizado, `UNIQUE (equipa_id, documento_idx)` |
| `nacionalidade` | char(2) | ISO 3166-1, não cifrado (baixa identificabilidade, serve estatística) |
| `morada` | `EncryptedStr` | opcional; nunca geocodificada, nunca no mapa |
| `contacto` | `EncryptedStr` | opcional |
| `notas` | `EncryptedText` | livre, com aviso no ecrã (§10) |
| `conservar_ate` | date | calculado, §7 |
| `anonimizada_em` | timestamptz | nulo enquanto viva |

**Não existe** — e uma migração que o adicione deve ser recusada em revisão:
saúde, origem étnica, religião, opiniões políticas, vida sexual, filiação
sindical, dados biométricos, "alcunha", "grupo", "perigosidade", "sinalizado".

### `veiculos`

`matricula` (`EncryptedStr`) + `matricula_idx` (HMAC, `UNIQUE (equipa_id,
matricula_idx)`), `marca`, `modelo`, `cor`, `observacoes` (cifrado),
`conservar_ate`, `anonimizado_em`.

### `registo_intervenientes`

Liga um registo a uma pessoa. É aqui que está o significado.

| Coluna | Notas |
|---|---|
| `registo_id`, `pessoa_id` | PK composta com `id` próprio para idempotência |
| `papel` | `identificado` \| `condutor` \| `passageiro` \| `testemunha` \| `denunciante` \| `ofendido` \| `suspeito` |
| `resultado` | `identificado` \| `notificado` \| `autuado` \| `detido` \| `sem_seguimento` |
| `referencia_oficial` | nº do auto/NUIPC que cobre esta pessoa |
| `observacoes` | cifrado |
| `conservar_ate` | derivado do papel + resultado (§7) |

### `registo_veiculos`

`registo_id`, `veiculo_id`, `papel` (`fiscalizado`, `interveniente`,
`abandonado`, `apreendido`), `referencia_oficial`, `observacoes`.

### `ident_activacoes` (o portão)

`equipa_id` (único, activo), `finalidade`, `base_legal` (enum:
`lei_59_2019` \| `rgpd`), `responsavel`, `referencia_autorizacao`,
`parecer_epd`, `aipd_referencia`, `prazos` (JSONB: prazo por papel/resultado),
`fotos_pessoa_permitidas` (bool, default `false`), `activada_por`, `activada_em`,
`revogada_em`, `revogada_por`, `motivo_revogacao`.

Uma linha activa (`revogada_em IS NULL`) é condição necessária para tudo o resto.
A revogação **não apaga** — congela: leitura continua possível para cumprir
prazos e responder a pedidos, escrita fica bloqueada.

### `ident_consultas` (o registo de acessos)

`utilizador_id`, `datahora`, `tipo` (`pesquisa` \| `abertura_ficha` \|
`dossier` \| `exportacao`), `criterio_idx` (o **HMAC** do termo pesquisado, nunca
o termo em claro), `pessoa_id` (quando aplicável), `motivo`, `resultado`
(`encontrado` \| `nao_encontrado` \| `negado`), `ip`, `user_agent`.
Append-only pelas mesmas garantias de `audit_logs` (`REVOKE UPDATE, DELETE`).

---

## 4. Como se chega a uma pessoa

Três caminhos, e mais nenhum:

**A. A partir de um registo próprio.**
`GET /api/registos/{id}` devolve os intervenientes. É o caminho normal: estou a
rever a minha fiscalização de ontem e vejo quem lá estava. Não pede motivo — o
motivo é o próprio registo, e a abertura fica na auditoria na mesma.

**B. Pesquisa por correspondência exacta.**
`POST /api/identificacoes/pesquisa` com `{criterio: "documento"|"matricula"|"nome",
valor, motivo}`. O servidor normaliza (`trim`, maiúsculas, sem acentos, sem
espaços duplos; matrícula sem hífenes), calcula
`HMAC-SHA256(IDENT_INDEX_KEY, criterio || ":" || valor_normalizado)` e faz
igualdade sobre a coluna `*_idx`. **Não há prefixo, não há semelhança, não há
"talvez seja este".** Quem pesquisa tem de saber o que procura — que é
precisamente o controlo de proporcionalidade.
Devolve no máximo os intervenientes dos registos da própria equipa.

**C. Ficha, vinda de A ou B.**
`GET /api/pessoas/{id}` — dados + lista dos registos onde aparece, **filtrada
por RLS** (só os da equipa). Exige `motivo` quando não vem imediatamente de A.

**Limites**: 30 pesquisas por hora e por utilizador (slowapi, mesmo padrão do
`escalasPT`); acima disso, 429 e aviso ao admin no painel. Sem exportação em
massa: o único export é o dossier de **uma** pessoa (§9), auditado.

**Porque é que o nome também é HMAC e não texto pesquisável**: um índice de nome
pesquisável por prefixo transforma isto num cadastro consultável — que é a
diferença entre "confirmo a pessoa que identifiquei" e "vejo o que há sobre este
sujeito". A primeira coisa é apoio ao serviço; a segunda é um sistema que
precisaria de um enquadramento que esta app não tem.

---

## 5. Cifra, chaves e acesso

- `IDENT_FIELD_KEY` — AES-GCM (via `TypeDecorator` `EncryptedStr`/`EncryptedText`),
  **distinta** de `FIELD_ENCRYPTION_KEY` (usada em `registos.descricao`) e de
  `ATTACHMENT_MASTER_KEY`. Um comprometimento parcial não abre o módulo.
- `IDENT_INDEX_KEY` — chave HMAC dos índices de pesquisa. Não decifra nada; sem
  ela não se consegue sequer testar hipóteses ("será que o cidadão X está aqui?")
  contra um dump roubado.
- Rotação: procedimento escrito em `docs/OPERACAO.md` — decifrar/recifrar em lote
  numa janela de manutenção, com `key_version` guardado em cada valor cifrado
  (prefixo de 1 byte), para a rotação ser incremental e não um big-bang.
- **2FA obrigatória** para qualquer utilizador com acesso ao módulo: sem TOTP
  activo, as rotas devolvem 403 mesmo com o portão aberto.
- **Step-up**: abrir uma ficha exige uma sessão com TOTP validado nas últimas 8 h;
  caso contrário, pede o código outra vez. Sessão de módulo curta, por desenho.
- Acesso por papel: `agente` vê as fichas ligadas aos **seus** registos;
  `chefe_equipa` vê as da equipa; `admin` **não vê fichas** — administra
  utilizadores, prazos e auditoria. Separar quem administra de quem consulta é o
  controlo mais barato que existe contra o abuso.

---

## 6. Offline — a excepção deliberada

O resto da app é offline-first. **Este módulo não é**, e é uma decisão, não uma
limitação:

- Criar/associar uma pessoa **exige rede**. Sem rede, a folha de registo aceita o
  registo normalmente e deixa os intervenientes por associar, com um aviso
  "por identificar (sem rede)" — e o registo fica na fila.
- O que existe localmente é uma escrita **pendente**, apagada do Dexie assim que
  o servidor confirma (`ack`) — nunca uma cópia de leitura.
- **Não há pesquisa offline de pessoas.** Um telemóvel com um índice de pessoas
  pesquisável é, na prática, um ficheiro no bolso, com o modelo de ameaça de um
  telemóvel (perda, apreensão, curiosidade alheia).
- `logout`, PIN falhado 5 vezes, ou 30 dias sem abrir ⇒ `Dexie.delete()` da store
  sensível.

Custo assumido: numa zona sem rede, a identificação anota-se no campo livre do
registo e associa-se depois, no fim do turno. Foi a troca escolhida.

---

## 7. Conservação e anonimização

`conservar_ate` calcula-se na criação do interveniente, a partir de `prazos` na
activação. Valores por omissão (configuráveis em `/admin`, nunca "sem prazo"):

| Situação | Prazo |
|---|---|
| Identificação sem seguimento | **90 dias** |
| Notificado / autuado (com `referencia_oficial`) | **1 ano** |
| Ofendido, testemunha, denunciante | **90 dias** |
| Suspeito / detido, com NUIPC | **1 ano** (o processo vive no sistema oficial) |
| Veículo fiscalizado | **90 dias** |

Trabalho diário: o que passou do prazo entra na **fila de conservação** em
`/admin`, junto com a dos registos. O João revê e confirma. Ao anonimizar:

1. `pessoas`: apaga-se `nome`, `nome_idx`, `numero_documento`, `documento_idx`,
   `data_nascimento`, `morada`, `contacto`, `notas`; fica `id`, `nacionalidade`,
   `anonimizada_em`.
2. `registo_intervenientes`: fica `papel`, `resultado`, `registo_id` — a
   estatística ("12 identificados, 3 autuados") sobrevive; a pessoa não.
3. Anexos com finalidade de pessoa: apagados do disco, com a linha de auditoria.
4. Tudo isto numa transacção, com `audit_logs` a guardar o **quê** (contagens,
   ids) e nunca o conteúdo apagado.

Uma pessoa cujo prazo expirou em todos os intervenientes é anonimizada; se
continuar ligada a um interveniente ainda dentro do prazo, mantém-se — e a fila
mostra a data mais tardia.

Aviso preventivo: 15 dias antes, o painel mostra quantas fichas vão expirar.
**Nada é apagado sozinho.** Nada fica para sempre.

---

## 8. Auditoria

Além do `audit_logs` geral, este módulo escreve em `ident_consultas` **em todos**
os caminhos de leitura: pesquisa (encontrada ou não), abertura de ficha, dossier,
exportação, e também as **negadas** (portão fechado, 2FA em falta, limite
excedido) — as negadas são as mais interessantes.

Ecrã `/admin/auditoria` com filtros por utilizador, data e tipo, e três números
que a página mostra sempre: consultas nos últimos 7 dias, utilizadores distintos,
e pesquisas sem resultado (um número alto de pesquisas falhadas é o padrão típico
de sondagem). O registo de acessos é para ser **olhado**, não só escrito.

---

## 9. Direitos dos titulares

Não se prevê atendimento directo na app — os pedidos entram pela GNR e pelo EPD.
O que a app tem de conseguir fazer, e faz:

- `GET /api/pessoas/{id}/dossier` — tudo o que existe sobre aquela pessoa (ficha,
  intervenientes, registos onde aparece, anexos com finalidade de pessoa), em
  JSON e PDF, para instruir a resposta. Auditado como `dossier`.
- `POST /api/pessoas/{id}/apagar` — apagamento fora de prazo, com `motivo`
  obrigatório e a mesma mecânica de anonimização da §7. Auditado, irreversível,
  só `chefe_equipa`.
- `POST /api/pessoas/{id}/rectificar` — correcção de dados errados, com o valor
  anterior guardado em `audit_logs.old_data` (cifrado) durante 1 ano.
- Limitação do tratamento: `estado = 'limitada'` — a ficha deixa de aparecer em
  pesquisas e só é legível por `chefe_equipa` com motivo, mas não é apagada
  enquanto a limitação durar.

---

## 10. Ecrãs

- **Activação** (`/admin/identificacoes`) — formulário do portão. Todos os campos
  da §3 obrigatórios; texto no topo a dizer, sem rodeios, que ligar isto cria um
  ficheiro de dados pessoais e quem passa a responder por ele. Botão de revogar
  sempre visível.
- **Intervenientes**, dentro da folha de registo — uma linha por pessoa: nome,
  documento, papel, resultado. Adicionar abre um formulário curto; se a pessoa já
  existe (documento igual), reutiliza a ficha em vez de duplicar.
- **Ficha** (`/pessoas/:id`) — dados, e a lista de registos onde aparece com data,
  tipo e referência do auto. Cabeçalho com `conservar_ate` e um aviso quando falta
  menos de 15 dias. Sem foto de rosto, sem "histórico de comportamento", sem
  campos de opinião.
- **Pesquisa** — um campo, um seletor de critério, um campo de motivo. O botão só
  activa com motivo preenchido. Zero resultados diz "sem correspondência exacta" e
  não sugere aproximações.
- O campo `notas` mostra, por baixo, uma linha permanente: *"Factos observados no
  serviço. Não escrever apreciações pessoais, saúde, origem, religião ou
  convicções."* É o único sítio onde o desenho não consegue impedir o mau uso —
  por isso avisa.

---

## 11. Testes que este módulo tem de ter

| Teste | O que garante |
|---|---|
| `test_portao_fechado_devolve_403` | Sem `ident_activacoes` activo, nenhuma rota funciona |
| `test_activacao_exige_todos_os_campos` | Não se liga o módulo com campos por preencher |
| `test_revogacao_bloqueia_escrita_mas_permite_leitura` | Congela, não apaga |
| `test_sem_2fa_devolve_403` | 2FA é condição, não sugestão |
| `test_pesquisa_sem_motivo_422` | Motivo obrigatório |
| `test_pesquisa_parcial_nao_encontra` | Não há `LIKE`: "Silv" não encontra "Silva" |
| `test_pesquisa_regista_hmac_nao_o_termo` | `ident_consultas.criterio_idx` nunca tem texto em claro |
| `test_pesquisa_negada_tambem_e_registada` | As negadas ficam |
| `test_rls_outra_equipa_404` | Isolamento por equipa |
| `test_rls_setting_vazio_nega` | O bug do `escalasPT` não se repete aqui |
| `test_admin_nao_le_fichas` | Separação administrar/consultar |
| `test_limite_consultas_por_hora` | 429 acima de 30/h |
| `test_anonimizacao_preserva_estatistica` | Contagens sobrevivem, pessoa não |
| `test_anonimizacao_apaga_anexos_do_disco` | Não fica ficheiro órfão |
| `test_dossier_inclui_tudo` | Direito de acesso executável |
| `test_dexie_limpa_pessoa_apos_ack` (Vitest) | Nada de pessoas em cache local |

---

## 12. O que fica de fora, e porquê

- **Reconhecimento facial e qualquer biometria** — §2 nº 3.
- **Ligação a bases oficiais** (SIIOP, SEF, registo automóvel) — não há integração,
  nem screen scraping, nem "colar aqui a consulta". O que vem do sistema oficial
  fica no sistema oficial; aqui fica a referência.
- **Partilha entre equipas ou exportação global** — RLS por equipa, sem excepção,
  sem endpoint de export total.
- **Alertas/marcações sobre pessoas** ("atenção a este") — é perfilagem, não é o
  que esta app é, e teria um enquadramento próprio.
- **Mapa de pessoas ou moradas** — o mapa é de registos (§8 do `PLANO.md`).

Se alguma destas precisar mesmo de existir, entra como decisão separada, com
fundamento escrito na activação — nunca como "aproveitando que já cá está".
