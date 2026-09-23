# Deploy no Vercel + Supabase

A app inteira corre no Vercel; a base de dados é o Postgres do Supabase.
Não é preciso VPS. O deploy com Docker (`deploy/docker-compose.prod.yml`)
continua a funcionar como antes: nada do que está aqui o altera.

```
browser ─┬─ /*              frontend estático (Vercel CDN)
         ├─ /api/*          FastAPI como Vercel Function (api/index.py)
         │                    ├─ Postgres ─► Supabase (pooler Supavisor, modo transação)
         │                    ├─ Redis    ─► Upstash (contadores de rate limit)
         │                    └─ sinais   ─► Supabase Realtime (REST broadcast)
         └─ wss://…supabase.co/realtime  notificações em tempo real
Vercel Cron ─► /api/internal/cleanup (diário)
```

## O que muda em relação ao Docker, e porquê

| No Docker | No Vercel | Porquê |
|---|---|---|
| WebSocket `/ws` na API | Supabase Realtime | Uma Function responde e termina. Não consegue manter um socket aberto, e cada instância só vê as suas próprias ligações. |
| Pool de 5–10 ligações | Uma ligação por pedido (`NullPool`), e o pooler do Supabase faz o pooling | Uma instância congelada entre pedidos fica com ligações mortas. |
| Prepared statements | Desligados (`statement_cache_size=0`, nomes únicos) | Em modo transação, pedidos seguidos podem cair em ligações diferentes do servidor. Testado com pgbouncer em modo transação: sem isto dá `DuplicatePreparedStatementError`. |
| Limpeza de tokens de hora a hora (loop) | Vercel Cron, 1×/dia às 04:00 UTC | Não há processo persistente. No plano Hobby, o cron corre no máximo uma vez por dia. |
| IP do cliente via nginx/uvicorn | Primeiro valor de `X-Forwarded-For` | O Vercel sobrescreve este cabeçalho na edge, por isso o cliente não o consegue escolher. |

### Realtime sem expor dados

Os canais do Realtime são públicos: qualquer pessoa com a chave publishable
pode entrar num canal se souber o nome. Por isso:

- O nome de cada canal é `HMAC(REALTIME_CHANNEL_SECRET, user/station id)`.
  O browser só fica a conhecer os seus próprios canais, através de
  `/api/realtime/config`, depois de autenticado.
- As mensagens não levam dados, só o tipo de evento (`notification`,
  `calendar_sync`). O browser vai buscar os dados à API, que verifica
  permissões como em qualquer outro pedido.
- Os sinais só são enviados depois do `COMMIT`. Se a transação falhar, os
  sinais são descartados.

### Data API do Supabase fechada

Por omissão, o Supabase dá aos papéis `anon` e `authenticated` acesso total a
todas as tabelas criadas em `public`. Na prática, a chave publishable (que vai
no bundle do frontend) conseguiria ler a tabela `users` pela API REST, com os
hashes de password incluídos. A migração `010` retira esses privilégios e
muda os privilégios por omissão, para que tabelas futuras também nasçam
fechadas. A app não usa essa API: liga ao Postgres diretamente como `postgres`.

O papel `postgres` do Supabase tem `BYPASSRLS`, tal como o superutilizador
no Docker. As políticas RLS da migração 007 comportam-se exatamente como hoje.

## Passos

### 1. Supabase

1. Cria um projeto (região `eu-west-3`, Paris, ou `eu-central-1`).
2. **Connect → Transaction pooler**: copia a connection string (porta
   `6543`). É o `DATABASE_URL` do Vercel.
3. **Connect → Session pooler** (porta `5432` no host `pooler`): usa esta
   para as migrações, a partir da tua máquina:

   ```bash
   cd backend
   DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-<região>.pooler.supabase.com:5432/postgres' \
   DATABASE_SSL=true APP_ENV=development JWT_SECRET_KEY=x \
     alembic upgrade head
   ```

   (Aceita o URL tal como o Supabase o dá. O `postgresql://` e o
   `?sslmode=` são convertidos automaticamente.)
4. **Project Settings → API Keys**: copia a *publishable key* e a *secret
   key*.
5. Opcional, mas recomendado: **Project Settings → Data API** → desativa-a.
   A migração 010 já fecha o acesso; desativar a API fecha a porta toda.

### 2. Redis (Upstash)

No projeto Vercel: **Storage → Marketplace → Upstash for Redis** e liga-o
ao projeto. A integração cria `REDIS_URL` (`rediss://…`), que a app usa
diretamente.

### 3. Vercel

1. *Add New → Project* e importa `joaaoazul/escalasPT`, com **Root
   Directory = raiz do repositório**. O `vercel.json` trata do resto: build
   do frontend, função Python em `api/index.py` e cron.
2. Environment Variables (Production e Preview):

   | Nome | Valor |
   |---|---|
   | `DATABASE_URL` | connection string do *Transaction pooler* (6543) |
   | `DATABASE_SSL` | `true` |
   | `REDIS_URL` | criado pela integração Upstash |
   | `JWT_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(64))"` |
   | `TOTP_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
   | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_…` |
   | `SUPABASE_SECRET_KEY` | `sb_secret_…` (marca como *Sensitive*) |
   | `REALTIME_CHANNEL_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `CRON_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `APP_ENV` | `production` |
   | `CORS_ORIGINS` | `[]` (o frontend e a API estão na mesma origem) |

   Email (SMTP) e Web Push (VAPID) funcionam como no Docker: as mesmas
   variáveis de `.env.example`.

   Não é preciso definir `SERVERLESS`: o Vercel define `VERCEL=1` e a app
   deteta-o sozinha.
3. Deploy.

### 4. Primeiro utilizador

O mesmo seed que o `deploy/setup.sh` corre no Docker, com o `DATABASE_URL`
(session pooler) do passo 1.3. As passwords vêm do ambiente, tal como no
`setup.sh`:

```bash
cd backend
read -rsp "Admin: " SEED_ADMIN_PASSWORD; echo
read -rsp "Comandante: " SEED_CMDT_PASSWORD; echo
read -rsp "Militares: " SEED_DEFAULT_PASSWORD; echo
export SEED_ADMIN_PASSWORD SEED_CMDT_PASSWORD SEED_DEFAULT_PASSWORD
DATABASE_URL='…' DATABASE_SSL=true APP_ENV=development JWT_SECRET_KEY=x \
  python -m scripts.seed
```

### 5. Verificar

- `https://<projeto>.vercel.app/api/health` → `{"status":"healthy","checks":{"database":"up","redis":"up"}}`
- Login e depois recarregar a página: a sessão mantém-se (cookie de refresh).
- DevTools → Network → WS: ligação a `<ref>.supabase.co/realtime/v1/websocket`.
- Cancela um turno publicado noutra janela: o militar recebe o toast sem
  recarregar a página.
- `curl https://<ref>.supabase.co/rest/v1/users -H "apikey: <publishable>"`
  devolve erro de permissão (ou 404 se desativaste a Data API), e nunca dados.
