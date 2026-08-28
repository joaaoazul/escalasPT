# Caderno de Serviço

Registo de serviço no terreno — ocorrências, fiscalizações e notas — a correr no
VPS próprio, acessível só pela tailnet, utilizável do telemóvel sem rede.

App nova. A arquitectura e a estética vêm do `escalasPT`; as oito correcções
conhecidas não vêm — estão descritas, com ficheiro e linha, em
[`docs/PLANO.md`](docs/PLANO.md) §1.2 e §1.3.

O plano completo e o desenho do módulo de identificações estão em
[`docs/PLANO.md`](docs/PLANO.md) e
[`docs/MODULO-IDENTIFICACOES.md`](docs/MODULO-IDENTIFICACOES.md).

---

## Estado

**Fase 0** — o esqueleto: autenticação completa, sistema de design herdado,
PWA instalável, RLS que nega por omissão, auditoria append-only a sério, docker,
migrações e CI.

Serviços, registos, fotos e sincronização offline são a fase 1.

| | |
|---|---|
| Backend | FastAPI 0.115, SQLAlchemy 2.0 async, Postgres 16, Redis 7, Alembic |
| Frontend | React 19, Vite 6, TypeScript 5.7, CSS puro com custom properties |
| Autenticação | JWT em memória + refresh HttpOnly com rotação e detecção de reutilização, TOTP, lockout, registo de sessões |
| Isolamento | RLS por `equipa_id` — contexto ausente **nega**, não permite |

---

## Correr localmente

```bash
cp .env.example .env          # ou: bash deploy/setup.sh, que gera tudo
docker compose up -d postgres redis

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
pytest                        # corre contra caderno_test, nunca contra a BD de dev
uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev                   # http://localhost:5173
```

Primeiro utilizador:

```bash
cd backend
CADERNO_SEED_PASSWORD='...' python -m scripts.seed \
    --equipa "Posto de Castro Marim" --codigo CTM \
    --username joao --nome "João Azul" --nip 1234567 --email joao@example.pt
```

---

## Pôr num servidor

Servidor limpo, do zero: [`deploy/SERVIDOR.md`](deploy/SERVIDOR.md) — o que
instalar (Docker, Tailscale, firewall, actualizações automáticas, e mais nada),
que máquina chega, cópias de segurança e restauro.

```bash
sudo bash deploy/provision.sh      # prepara o servidor
sudo tailscale up --ssh
bash deploy/setup.sh               # gera segredos, constrói, migra, sobe
sudo tailscale serve --bg 8090
sudo bash deploy/install-backups.sh
```

O nginx só escuta em `127.0.0.1:8090`; quem publica é o `tailscale serve`, que
termina TLS com o certificado `*.ts.net` da máquina. Isso dá um certificado
válido e, portanto, **contexto seguro** — sem o qual não há service worker, nem
câmara, nem GPS. Não há porta aberta para a internet, nem Funnel.

A ordem importa e não é negociável:

```
build → alembic upgrade head → up -d --wait
```

> O `docker compose up -d` e o `alembic upgrade` correm na máquina; o
> `deploy/setup.sh` faz os dois pela ordem certa.

---

## O que é diferente do `escalasPT`, e porquê

| | |
|---|---|
| A app liga-se com `caderno_app`, não com o dono das tabelas | Sem isso, o `REVOKE` no `audit_logs` e a RLS não se aplicam — que é o que acontece hoje no `escalasPT` |
| Policy RLS: contexto vazio **nega** | No `escalasPT`, `current_setting(...) = ''` dá bypass total |
| `TEST_DATABASE_URL` obrigatório e validado | O `conftest.py` do `escalasPT` faz `drop_all` na BD apontada pelo `.env` |
| `Permissions-Policy: camera=(self), geolocation=(self)` | O `escalasPT` envia `camera=(), geolocation=()` — nesta app, a câmara e o GPS deixariam de funcionar |
| CSP com `worker-src blob:` e `img-src blob:` | Service worker, workers do mapa e miniaturas locais das fotos |
| Outfit auto-alojada em woff2 | O CSP bloqueia o Google Fonts; a app perderia a letra, sem erro visível |
| Ícones PNG 192/512 + maskable | Um SVG único não serve para o ícone do ecrã inicial |
| A revogação por reutilização de refresh token faz `commit()` antes de levantar | No `escalasPT` o rollback do pedido desfaz a revogação e a auditoria: responde "sessão invalidada" sem invalidar nada |
| CI com `pytest` e `npm run build` | Hoje só há Bandit e pip-audit |

Cada uma tem um teste que falha se regredir — ver `backend/tests/`.
