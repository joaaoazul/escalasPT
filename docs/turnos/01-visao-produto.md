# 1. Visão de produto

## 1.1 Problema

Quem trabalha por turnos (saúde, forças de segurança, bombeiros, indústria, retalho, hotelaria, aviação,
call centers) vive num calendário que **não encaixa nas apps de calendário normais**:

- Os turnos seguem **ciclos** (4×4, 12h dia/noite, `MMTTNNFFFF`, 5×2 com rotação semanal) e não semanas fixas.
- Um turno da noite **atravessa a meia-noite** e pertence ao dia em que começa.
- É preciso saber **quantas horas** se fez, quantas são noturnas/feriado/extra e **quanto se vai receber**.
- Trocas de turno entre colegas são combinadas por WhatsApp e ficam perdidas.
- A família precisa de saber "quando é que estás de folga?".

O EscalasPT resolveu parte disto para um posto da GNR, mas acoplado a uma hierarquia (Comando → Destacamento → Posto)
e a um fluxo *top-down* (o comandante cria e publica). O **Turnos** inverte o modelo: **cada pessoa é dona do seu calendário**,
e a colaboração é opcional e horizontal.

## 1.2 Personas

| Persona | Contexto | O que precisa |
|---------|----------|---------------|
| **Ana, enfermeira** | Rotação `M M T T N N F F F F`, 2 hospitais | Aplicar rotação de uma vez, 2 calendários, contar horas por hospital, lembrete 1h antes |
| **Rui, agente de segurança** | Escala enviada em papel todo o mês | Pintar o mês em 30 segundos, marcar gratificados/extra, ver valor a receber |
| **Marta, operadora fabril** | Equipa de 12 pessoas, trocas frequentes | Ver "quem está hoje", propor troca, colega aceita, fica registado |
| **João, companheiro da Ana** | Não trabalha por turnos | Subscrever o calendário dela no Google Calendar (só leitura) |
| **Sofia, chefe de equipa informal** | Coordena a equipa num grupo | Ver o roster do grupo, aprovar trocas se a política o exigir, exportar PDF |

## 1.3 Princípios de produto

1. **Personal-first** — a app tem de ser útil a uma pessoa sozinha, no primeiro minuto, sem convites nem configuração de empresa.
2. **Registar um mês inteiro em < 1 minuto** — modo pincel + rotações.
3. **Mobile-first, offline-tolerante** — consulta-se o turno de amanhã no autocarro, sem rede.
4. **Colaboração horizontal** — grupos e trocas entre pares; aprovação é uma *política opcional* do grupo, não uma hierarquia.
5. **Os números têm de bater certo** — horas, noturno, feriados e remuneração calculados de forma determinística e auditável.
6. **Privacidade por omissão** — nada é partilhado sem ação explícita; detalhe granular (ver só "ocupado/livre" vs. detalhes).

## 1.4 O que sai, o que fica, o que entra (vs. EscalasPT)

### Sai
| EscalasPT | Motivo |
|-----------|--------|
| `Station` com `comando_territorial`, `destacamento` | Hierarquia organizacional específica da GNR |
| Papéis `COMANDANTE`, `ADJUNTO`, `SECRETARIA`, `MILITAR` | Substituídos por posse do calendário + papéis de grupo genéricos |
| Estados `DRAFT → PUBLISHED` de turnos | Só fazia sentido com alguém a publicar para terceiros |
| `nip`, `numero_ordem`, `grat_type`, códigos fixos (`GRAT`, `FER`, `CONV`, …) em código | Específicos do domínio militar; passam a ser **dados configuráveis** (tipos de turno com `kind`) |
| Onboarding de posto pelo admin | Registo self-service |

### Fica (reimplementado e melhorado)
| Funcionalidade | Melhoria |
|----------------|----------|
| Tipos de turno com cor/código/horário | + ícone, pausas, duração explícita, `kind` (trabalho/ausência/folga/prevenção), taxa remuneratória, lembretes por tipo |
| Deteção de conflitos (sobreposição, dia inteiro, descanso mínimo) | Sobreposição garantida **na BD** (`EXCLUDE`); regras configuráveis por calendário; avisos vs. erros |
| Trocas de turno | Trocas diretas, **ofertas abertas** ao grupo ("dou este turno"), pedidos "preciso que me cubram", política de aprovação por grupo, expiração automática |
| Notificações in-app + Web Push + email | **Outbox transacional** (nunca se perde uma notificação), preferências por tipo/canal, horas de silêncio |
| Tempo real (WebSocket) | SSE simples + Redis pub/sub para múltiplas instâncias |
| Relatórios PDF | + CSV/Excel, + **feed ICS** subscrevível |
| Auditoria imutável | Mantém-se, por grupo e por calendário |
| 2FA TOTP, bloqueio de conta, sessões | + **passkeys (WebAuthn)**, login Google/Apple |

### Entra (novo)
- **Múltiplos calendários** por utilizador (ex.: dois empregos, ou gerir o calendário de um familiar).
- **Rotações/padrões** com ciclo arbitrário, aplicadas a um intervalo de datas, com *overrides* por dia.
- **Modo pincel**: escolhe-se um tipo de turno e toca-se nos dias.
- **Feriados** nacionais e municipais de Portugal (e extensível a outros países).
- **Horas & remuneração**: taxa base, majoração noturna/fim de semana/feriado, horas extra, banco de horas.
- **Saldos de ausências** (dias de férias por ano, consumidos vs. disponíveis).
- **Notas de dia** e etiquetas.
- **Estatísticas**: horas por mês, distribuição por tipo, noites, fins de semana trabalhados, heatmap anual.
- **Partilha**: link ICS privado, partilha de calendário com outra conta (ver / editar / só disponibilidade).
- **Vista de grupo (roster)**: matriz pessoas × dias, "quem está a trabalhar hoje/agora".
- **Importação** de CSV/ICS e **exportação** PDF/CSV/ICS.
- **i18n** (pt-PT por omissão, en) e **tema claro/escuro**.

## 1.5 Catálogo de funcionalidades

Prioridade: **M** = MVP, **S** = logo a seguir (v1.1), **C** = mais tarde.

### Calendário
| ID | Funcionalidade | Prio |
|----|----------------|------|
| CAL-01 | Vista mensal com "chips" coloridos por turno, feriados e notas | M |
| CAL-02 | Vista semanal/diária em grelha horária (turnos noturnos a atravessar a meia-noite) | M |
| CAL-03 | Vista agenda (lista dos próximos turnos) | M |
| CAL-04 | Vista anual (heatmap) | S |
| CAL-05 | Modo pincel: selecionar tipo → tocar/arrastar sobre dias | M |
| CAL-06 | Criar/editar turno pontual (hora personalizada, notas, extra) | M |
| CAL-07 | Arrastar e largar turnos entre dias (desktop) | S |
| CAL-08 | Desfazer/refazer (últimas 20 operações da sessão) | S |
| CAL-09 | Múltiplos calendários, com sobreposição visual opcional | M |
| CAL-10 | Notas de dia e etiquetas | M |

### Tipos de turno e rotações
| ID | Funcionalidade | Prio |
|----|----------------|------|
| TYP-01 | CRUD de tipos de turno (nome, abreviatura ≤ 4 chars, cor, ícone, início, duração, pausa, `kind`) | M |
| TYP-02 | Modelos iniciais (Manhã/Tarde/Noite/Folga/Férias/Baixa) ao criar calendário | M |
| ROT-01 | Definir rotação com ciclo de N dias | M |
| ROT-02 | Aplicar rotação a intervalo (com "começar no dia X do ciclo") e pré-visualizar | M |
| ROT-03 | Reaplicar/alterar rotação preservando *overrides* manuais | S |
| ROT-04 | Biblioteca de rotações comuns (4×4, 2-2-3 "Pitman", 5×2, 24×48, 12h D/N) | S |

### Regras e validação
| ID | Funcionalidade | Prio |
|----|----------------|------|
| RUL-01 | Sobreposição de turnos proibida (erro) | M |
| RUL-02 | Tipo de "dia inteiro" (férias, baixa, folga) exclusivo no dia (erro, configurável) | M |
| RUL-03 | Descanso mínimo entre turnos (aviso; horas configuráveis) | M |
| RUL-04 | Máximo de horas semanais / dias consecutivos (aviso) | S |

### Horas, dinheiro e ausências
| ID | Funcionalidade | Prio |
|----|----------------|------|
| PAY-01 | Horas por período (dia/semana/mês/ano), por tipo | M |
| PAY-02 | Perfil remuneratório: taxa base, majorações noturna/fim de semana/feriado, extra | S |
| PAY-03 | Banco de horas (objetivo mensal vs. real) | S |
| ABS-01 | Saldos anuais de ausências por tipo (ex.: 22 dias de férias) | S |
| HOL-01 | Feriados nacionais PT + municipais (por concelho) + manuais | M |

### Grupos e trocas
| ID | Funcionalidade | Prio |
|----|----------------|------|
| GRP-01 | Criar grupo, convidar por link/código/email, papéis OWNER/ADMIN/MEMBER | M |
| GRP-02 | Cada membro escolhe **que calendário** partilha e com que detalhe | M |
| GRP-03 | Roster do grupo (pessoas × dias), "quem está hoje/agora" | M |
| SWP-01 | Pedido de troca direta (o meu turno ↔ turno do colega) | M |
| SWP-02 | Oferta aberta ao grupo ("dou/troco este turno"); vários colegas podem responder | S |
| SWP-03 | Política do grupo: `PEER_ONLY` ou `ADMIN_APPROVAL` | M |
| SWP-04 | Expiração automática quando o turno começa | M |
| SWP-05 | Comprovativo PDF da troca | S |
| GRP-04 | Registo de atividade do grupo (auditoria) | S |

### Notificações e integrações
| ID | Funcionalidade | Prio |
|----|----------------|------|
| NOT-01 | Centro de notificações in-app, tempo real | M |
| NOT-02 | Web Push (PWA) | M |
| NOT-03 | Lembretes antes do turno (por tipo, ex.: 60 min) | M |
| NOT-04 | Email (convites, trocas, resumo semanal opcional) | S |
| NOT-05 | Preferências por tipo × canal, horas de silêncio | S |
| INT-01 | Feed ICS privado (webcal://) por calendário | M |
| INT-02 | Exportação PDF (mês) e CSV | S |
| INT-03 | Importação CSV/ICS | C |
| INT-04 | App móvel nativa (React Native/Expo) reutilizando a API | C |

### Conta
| ID | Funcionalidade | Prio |
|----|----------------|------|
| ACC-01 | Registo/login email+password, verificação de email, recuperação | M |
| ACC-02 | Login Google / Apple (OIDC) | S |
| ACC-03 | 2FA TOTP + passkeys | S |
| ACC-04 | Gestão de sessões/dispositivos | M |
| ACC-05 | Exportar os meus dados / apagar conta (RGPD) | M |

## 1.6 Âmbito do MVP (o "fio condutor")

> Uma pessoa regista-se, cria o calendário, aplica a sua rotação para os próximos 3 meses, ajusta 2 dias com o pincel,
> vê as horas do mês, subscreve o calendário no telemóvel via ICS, cria um grupo com colegas, e troca um turno com
> um colega que aceita — recebendo push em cada passo.

Tudo o que está marcado **M** acima. Critérios de aceitação transversais:

- p95 < 200 ms nas leituras do calendário mensal (1 calendário, 60 turnos).
- Funciona em ecrã de 360 px de largura sem scroll horizontal.
- Lighthouse PWA/Accessibility ≥ 90.
- Nenhum cálculo de horas errado nos dias de mudança de hora (último domingo de março/outubro) — coberto por testes.

## 1.7 Métricas de sucesso

- **Ativação**: % de registos que criam ≥ 10 turnos nas primeiras 24 h (alvo 60%).
- **Retenção D30** (alvo 40%) — calendário de turnos é uso diário por natureza.
- **Colaboração**: % de utilizadores ativos em pelo menos um grupo; nº de trocas concluídas/mês.
- **Tempo até mês completo**: mediana < 60 s (instrumentado no frontend).
