# Frontend no Vercel

O frontend (React/Vite) é servido pelo Vercel; a API, o Postgres e o Redis
continuam no VPS, atrás do Caddy partilhado.

```
browser ──► <projeto>.vercel.app ──┬─ /*        ficheiros estáticos (Vercel)
                                   └─ /api/*    rewrite ─► escalas.joaoazul.dev/api/* (Caddy → nginx → FastAPI)
browser ──► wss://escalas.joaoazul.dev/ws   (direto, o Vercel não faz proxy de WebSockets)
```

Porque é que é assim:

- **`/api` via rewrite, não CORS.** Para o browser, a API fica na mesma
  origem que a página. O cookie `refresh_token` (`SameSite=Strict`,
  `Path=/api/auth`) continua a funcionar sem alterações ao backend, e
  `CORS_ORIGINS` não precisa de mudar.
- **WebSocket direto.** As rewrites do Vercel não fazem upgrade de ligações.
  O socket liga a `VITE_WS_URL`. A autenticação é feita com o token na
  primeira mensagem, por isso não depende de cookies nem da origem.
- **`X-Escalas-Proxy-Secret`.** Os pedidos que chegam via Vercel vêm de IPs
  da edge do Vercel, e o Vercel não publica uma lista estável desses IPs.
  O `vercel.json` carimba cada pedido com um secret. O Caddy só confia no
  `X-Real-IP` enviado pelo Vercel quando o secret está certo. Sem isto,
  todos os utilizadores partilhavam o mesmo bucket de rate limit (login:
  5/min para todos).

## Passos

### 1. Gerar o secret

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Usa o mesmo valor no VPS e no Vercel. Tem de ter pelo menos 32 caracteres;
abaixo disso, o Caddy ignora-o.

### 2. VPS: Caddy

1. Copia o bloco `escalas.joaoazul.dev { … }` atualizado de
   `deploy/Caddyfile` para o Caddyfile da stack partilhada.
2. Adiciona `ESCALAS_PROXY_SECRET=<secret>` ao `environment:` do serviço
   Caddy nessa stack. `{$ESCALAS_PROXY_SECRET}` é lido quando o Caddyfile
   carrega, por isso recria o contentor (`docker compose up -d caddy`);
   um simples `caddy reload` não chega para apanhar uma variável nova.
3. Confirma: `docker exec <caddy> caddy validate --config /etc/caddy/Caddyfile`.

Faz isto **antes** do passo 3. Sem o secret configurado no Caddy, a app
funciona na mesma, mas com o rate limit partilhado.

### 3. Vercel: projeto

1. *Add New → Project* e importa `joaaoazul/escalasPT`.
2. **Root Directory: `frontend`**. É aí que está o `vercel.json`; o preset
   Vite é detetado sozinho.
3. Environment Variables (Production e Preview):

   | Nome                   | Valor                              |
   |------------------------|------------------------------------|
   | `ESCALAS_PROXY_SECRET` | o secret do passo 1 (Sensitive)    |
   | `VITE_WS_URL`          | `wss://escalas.joaoazul.dev/ws`    |

4. Deploy.

### 4. Verificar

- `https://<projeto>.vercel.app/api/health` devolve
  `{"status":"healthy",…}`.
- O login funciona e, depois de recarregar a página, a sessão mantém-se
  (isto prova que o cookie de refresh passa pelo rewrite).
- Nas DevTools → Network → WS, a ligação a `escalas.joaoazul.dev/ws` fica aberta.
- No VPS, `docker logs escalaspt-nginx` mostra os IPs reais dos visitantes
  na primeira coluna dos pedidos `/api`, e não IPs do Vercel.

## Se mudares o domínio da API

O host está em dois sítios: no `dest` e no `connect-src` da CSP em
`frontend/vercel.json`, e na variável `VITE_WS_URL`.
