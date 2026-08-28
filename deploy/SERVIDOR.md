# O que meter num servidor limpo

Resposta curta: **Docker, Tailscale, firewall, actualizações automáticas — e mais
nada.** Tudo o resto corre em contentor. Não se instala Postgres, nem Redis, nem
nginx, nem Node, nem Python no anfitrião; não se instala certbot nem se abre a
porta 443, porque o TLS é do `tailscale serve`.

O `deploy/provision.sh` faz o de cima num comando. Este documento é o que ele
faz, por que ordem, e o que fica por fazer à mão.

---

## 1. Que máquina chega

| | Mínimo | Confortável |
|---|---|---|
| vCPU | 2 | 2–4 |
| RAM | 2 GB (+ 2 GB de swap) | 4 GB |
| Disco | 20 GB | 40–80 GB |
| SO | Debian 12 ou Ubuntu 22.04/24.04 LTS, 64 bits | igual |

Os limites do `docker-compose.yml` somam ~1,6 GB: Postgres 512 MB, API 768 MB,
Redis 192 MB, nginx 128 MB. Com 2 GB de RAM corre, mas o `npm ci` do build do
frontend é o que aperta — daí o `provision.sh` criar 2 GB de swap abaixo de 4 GB.

**O disco é o que cresce**, e cresce por causa das fotografias: os registos em si
são texto. Uma fotografia de telemóvel comprimida anda em 2–4 MB; a 10 fotos por
turno, são ~1 GB por ano por pessoa. 20 GB chega para começar, mas escolhe um
plano onde o disco se possa aumentar.

Arquitectura: **x86-64 ou ARM64**, ambas servem (as imagens usadas têm as duas).

---

## 2. O que é instalado, e porquê

| Pacote | Para quê |
|---|---|
| `docker-ce` + `docker-compose-plugin` | Corre a app. Do repositório oficial da Docker, não o `docker.io` da distribuição — esse vem atrasado e sem o `compose` v2 |
| `tailscale` | A rede privada e o certificado TLS. É o que torna a app alcançável e, ao mesmo tempo, invisível da internet |
| `ufw` | Segunda linha do firewall |
| `unattended-upgrades` | Actualizações de segurança sozinhas, com reinício às 05:30 |
| `age` | Cifra das cópias de segurança |
| `git`, `curl`, `openssl`, `python3` | Clonar o repositório e gerar segredos no `setup.sh` |
| `chrony` | Relógio certo. O TOTP falha com uns minutos de desvio, e as horas dos registos passam a ser discutíveis |

E o que **não** se instala, de propósito: nginx ou apache no anfitrião (o nginx
está em contentor), certbot (não há domínio público), Postgres/Redis no
anfitrião (ficam em contentor, isolados), Portainer, painéis de gestão, Node.
Cada um destes é mais uma coisa a actualizar e mais uma porta a fechar.

---

## 3. Preparar o servidor

```bash
# no servidor, como utilizador com sudo
git clone <repo> /opt/caderno/app
cd /opt/caderno/app
sudo bash deploy/provision.sh
```

Fecha o porto 22 à internet por omissão. Se ainda não tens o Tailscale a
funcionar e não queres ficar de fora, corre `sudo bash deploy/provision.sh
--keep-ssh` e fecha o 22 mais tarde com `sudo ufw delete allow 22/tcp`.

Depois, ligar à tailnet:

```bash
sudo tailscale up --ssh
```

Abre um link para autenticar. O `--ssh` põe o SSH a passar pelo Tailscale, com a
identidade da tailnet — é o que permite fechar o 22 e deixar de ter um servidor
a apanhar tentativas de login o dia inteiro.

Sair da sessão e voltar a entrar (para o grupo `docker` valer), e confirmar:

```bash
docker run --rm hello-world
tailscale status
```

---

## 4. Subir a app

```bash
cd /opt/caderno/app
bash deploy/setup.sh
```

Gera os segredos em `.env` (600), constrói a imagem da API, constrói o frontend
para o volume que o nginx serve, sobe a base de dados, corre
`alembic upgrade head` e só depois levanta a stack. **Esta ordem não é decorativa**:
subir a API antes da migração dá um serviço que responde 500 com healthcheck
verde.

---

## 5. Publicar na tailnet

```bash
sudo tailscale serve --bg 8090
tailscale serve status
```

O nginx escuta em `127.0.0.1:8090`; quem publica é o `tailscale serve`, que
termina TLS com o certificado `*.ts.net` da máquina. Resultado:
`https://<maquina>.<tailnet>.ts.net`, com certificado válido — e portanto
**contexto seguro**, sem o qual não há service worker, nem câmara, nem GPS.

Não usar `tailscale funnel`: isso põe a app na internet, que é exactamente o que
este desenho evita.

---

## 6. Primeiro utilizador

```bash
cd /opt/caderno/app
CADERNO_SEED_PASSWORD='<palavra-passe forte>' \
docker compose run --rm api python -m scripts.seed \
    --equipa "Posto de Castro Marim" --codigo CTM \
    --username joao --nome "João Azul" --nip 1234567 --email joao@example.pt
```

A palavra-passe vai por variável de ambiente, não por argumento — argumentos
ficam no histórico da shell e na lista de processos. Mínimo 12 caracteres com
maiúscula, minúscula, algarismo e símbolo; o script recusa o resto.

---

## 7. Cópias de segurança

```bash
sudo bash deploy/install-backups.sh
```

Gera um par de chaves `age`, **imprime a chave privada uma única vez** e apaga-a
do servidor. Guarda-a no gestor de palavras-passe: sem ela não há restauro. Fica
só a chave pública, que serve para cifrar e não para decifrar — quem levar o
servidor leva cópias que não consegue abrir.

Depois instala um temporizador systemd (03:30, com atraso aleatório) e corre uma
cópia imediatamente, para provar que funciona. Cada noite:

1. `pg_dump -Fc` da base de dados;
2. arquivo dos anexos (a partir da fase 1);
3. **verificação**: o dump tem de ser legível pelo `pg_restore --list` e ter
   dados de pelo menos uma tabela;
4. cifra para a chave pública;
5. `backups/ESTADO.json` com a hora e o tamanho — é isto que o painel de
   administração vai ler para mostrar a idade da última cópia boa (fase 4);
6. apaga o que tem mais de 30 dias.

No MAIA os backups estiveram sete dias parados sem ninguém dar por isso. Por isso
é que o passo 3 e o passo 5 existem.

**Restaurar** (fazer isto uma vez, agora, antes de precisares a sério):

```bash
age -d -i chave-privada.txt caderno-20260828T033000Z.tar.age > caderno.tar
tar -xf caderno.tar                     # base.dump + anexos.tar.gz

docker compose exec -T postgres \
    pg_restore -U "$POSTGRES_USER" -d caderno --clean --if-exists < base.dump

docker run --rm -v caderno_anexos:/anexos -v "$PWD:/in" alpine \
    tar -xzf /in/anexos.tar.gz -C /anexos
```

Levar uma cópia para fora do servidor é o passo que falta e que nenhum script faz
sozinho: `tailscale file cp` para a tua máquina, ou um `rclone` para
armazenamento externo. Uma cópia que só existe no servidor não protege do que
mata servidores.

---

## 8. Manutenção

| Quando | O quê |
|---|---|
| Automático | Actualizações de segurança do sistema, reinício às 05:30 se preciso |
| Automático | Cópia nocturna com verificação |
| Automático | Limpeza horária de tokens expirados e sessões revogadas (na app) |
| Mensal | `docker compose pull && bash deploy/setup.sh` para actualizar as imagens |
| Mensal | Confirmar `cat /opt/caderno/backups/ESTADO.json` e o espaço em disco |
| Trimestral | Restaurar uma cópia para uma base de dados de teste. Uma cópia nunca restaurada é uma hipótese |

Ver o que se passa:

```bash
docker compose ps
docker compose logs -f api
systemctl list-timers caderno-backup.timer
journalctl -u caderno-backup.service -n 50
df -h /
```

---

## 9. Quando alguma coisa corre mal

**Não abre no telemóvel.** `tailscale serve status` no servidor e `tailscale
status` no telemóvel — os dois têm de estar na mesma tailnet. O endereço é o
`https://…ts.net`, não o `100.x.x.x`: por IP não há certificado, e sem
certificado a PWA e a câmara não funcionam.

**Abre mas a câmara não faz nada.** Confirmar que o endereço é `https://` e que
os cabeçalhos estão certos:

```bash
curl -sI https://<maquina>.<tailnet>.ts.net/api/health | grep -i permissions-policy
```

Tem de dizer `camera=(self)`. Se disser `camera=()`, alguém copiou os cabeçalhos
do escalasPT por cima (docs/PLANO.md §1.3).

**A API não arranca.** `docker compose logs api`. Quase sempre é o `.env`:
segredo em falta, ou a migração não correu. `docker compose run --rm --no-deps
api alembic current` diz em que versão está a base de dados.

**Disco cheio.** Por esta ordem: `du -sh /var/lib/docker`, `docker system prune
-a` (imagens antigas), `du -sh /opt/caderno/backups`, e o volume dos anexos.

**Perdeste o acesso SSH depois de fechar o 22.** A consola do fornecedor do VPS
continua a funcionar; entra por lá e `sudo ufw allow 22/tcp`.

---

## 10. Resumo, para copiar

```bash
git clone <repo> /opt/caderno/app && cd /opt/caderno/app
sudo bash deploy/provision.sh          # docker, tailscale, firewall, swap
sudo tailscale up --ssh                # autenticar no link que aparece
# sair e voltar a entrar (grupo docker)
bash deploy/setup.sh                   # segredos, build, migrações, up
sudo tailscale serve --bg 8090         # TLS e endereço ts.net
sudo bash deploy/install-backups.sh    # chaves + temporizador + primeira cópia
# e criar o primeiro utilizador (§6)
```
