#!/usr/bin/env bash
# ============================================================
# Caderno de Serviço — cópia de segurança nocturna
#
#   bash deploy/backup.sh
#
# Faz o dump da base de dados, arquiva os anexos, verifica que o dump é
# legível, cifra para a chave pública que está no servidor, e escreve o estado
# em backups/ESTADO.json — que é o que o painel de administração lê para
# mostrar a idade da última cópia boa.
#
# A chave privada NÃO está aqui. Foi impressa uma vez pelo install-backups.sh e
# guardada fora do servidor. Uma cópia cifrada com a chave de decifra ao lado
# não é uma cópia de segurança, é um ficheiro maior.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${CADERNO_BACKUP_DIR:-/opt/caderno/backups}"
PUBKEY_FILE="$BACKUP_DIR/backup-key.pub"
ESTADO="$BACKUP_DIR/ESTADO.json"
RETENTION_DAYS="${CADERNO_BACKUP_RETENTION_DAYS:-30}"

COMPOSE="docker compose -f $APP_DIR/docker-compose.yml --env-file $APP_DIR/.env"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# shellcheck disable=SC1091
set -a; . "$APP_DIR/.env"; set +a

fail() {
    printf '{"estado":"falhou","quando":"%s","erro":%s}\n' \
        "$(date -u +%FT%TZ)" "$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')" \
        > "$ESTADO"
    echo "ERRO: $1" >&2
    exit 1
}

mkdir -p "$BACKUP_DIR"
[[ -f "$PUBKEY_FILE" ]] || fail "Sem chave pública em $PUBKEY_FILE — correr deploy/install-backups.sh"

# ── Base de dados ────────────────────────────────────────────
# Formato custom (-Fc): permite pg_restore selectivo e traz compressão.
$COMPOSE exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "${POSTGRES_DB:-caderno}" \
    > "$TMP/base.dump" 2>"$TMP/erro.log" || fail "pg_dump falhou: $(tail -3 "$TMP/erro.log")"

# Verificar antes de cifrar — um dump truncado passa despercebido durante meses.
pg_restore --list "$TMP/base.dump" > "$TMP/indice.txt" 2>/dev/null \
    || docker run --rm -i -v "$TMP:/w" postgres:16-alpine \
       pg_restore --list /w/base.dump > "$TMP/indice.txt" 2>/dev/null \
    || fail "o dump não é legível pelo pg_restore"

TABELAS="$(grep -c 'TABLE DATA' "$TMP/indice.txt" || true)"
[[ "$TABELAS" -gt 0 ]] || fail "o dump não tem dados de nenhuma tabela"

# ── Anexos (a partir da fase 1) ──────────────────────────────
if docker volume inspect caderno_anexos >/dev/null 2>&1; then
    docker run --rm -v caderno_anexos:/anexos:ro -v "$TMP:/saida" alpine \
        tar -czf /saida/anexos.tar.gz -C /anexos . \
        || fail "não consegui arquivar os anexos"
else
    : > "$TMP/anexos.tar.gz"   # ainda não existem — fase 1
fi

# ── Empacotar e cifrar ───────────────────────────────────────
tar -cf "$TMP/caderno-$STAMP.tar" -C "$TMP" base.dump anexos.tar.gz
DESTINO="$BACKUP_DIR/caderno-$STAMP.tar.age"

if command -v age >/dev/null; then
    age -R "$PUBKEY_FILE" -o "$DESTINO" "$TMP/caderno-$STAMP.tar" || fail "a cifra falhou"
else
    fail "o age não está instalado (deploy/provision.sh instala-o)"
fi

chmod 600 "$DESTINO"
TAMANHO="$(stat -c %s "$DESTINO")"
[[ "$TAMANHO" -gt 1024 ]] || fail "a cópia tem $TAMANHO bytes — demasiado pequena para ser verdade"

# ── Estado e limpeza ─────────────────────────────────────────
printf '{"estado":"ok","quando":"%s","ficheiro":"%s","bytes":%s,"tabelas":%s}\n' \
    "$(date -u +%FT%TZ)" "$(basename "$DESTINO")" "$TAMANHO" "$TABELAS" > "$ESTADO"

find "$BACKUP_DIR" -name 'caderno-*.tar.age' -mtime "+$RETENTION_DAYS" -delete

echo "Cópia feita: $DESTINO ($((TAMANHO / 1024)) KB, $TABELAS tabelas)"
