#!/usr/bin/env bash
# ============================================================
# Caderno de Serviço — deployment
#   bash deploy/setup.sh            first run / update
#   bash deploy/setup.sh --reset    destroy everything and start over
#
# Migration order matters and is not negotiable:
#   build → alembic upgrade head → up -d --wait
# Bringing the API up before the migration is how you get a half-started stack
# that healthchecks green and answers 500.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
COMPOSE="docker compose -f $PROJECT_DIR/docker-compose.yml --env-file $ENV_FILE"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERRO]${NC} $*" >&2; }

command -v docker >/dev/null 2>&1 || { error "Docker não está instalado"; exit 1; }
docker compose version >/dev/null 2>&1 || { error "Docker Compose v2 não está instalado"; exit 1; }

# ── Reset ────────────────────────────────────────────────────
if [[ "${1:-}" == "--reset" ]]; then
    warn "RESET: apaga a base de dados, o Redis e o frontend construído."
    read -rp "Escrever 'sim' para confirmar: " CONFIRM
    [[ "$CONFIRM" == "sim" ]] || { info "Abortado."; exit 0; }
    $COMPOSE down -v 2>/dev/null || docker compose -f "$PROJECT_DIR/docker-compose.yml" down -v || true
    rm -f "$ENV_FILE"
    info "Reset feito."
fi

# ── Secrets ──────────────────────────────────────────────────
gen_fernet() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
        || docker run --rm python:3.12-slim sh -c \
           "pip install --quiet cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
}

if [[ ! -f "$ENV_FILE" ]]; then
    info "A gerar .env com segredos novos..."
    cp "$PROJECT_DIR/.env.example" "$ENV_FILE"

    PG_PASS="$(openssl rand -hex 24)"
    APP_DB_PASS="$(openssl rand -hex 24)"
    REDIS_PASS="$(openssl rand -hex 16)"
    JWT_SECRET="$(openssl rand -hex 32)"

    # Hex only: these end up inside URLs, and a '/' or '@' in a password turns
    # a working DSN into a two-hour debugging session.
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|"                 "$ENV_FILE"
    sed -i "s|^CADERNO_APP_DB_PASSWORD=.*|CADERNO_APP_DB_PASSWORD=${APP_DB_PASS}|" "$ENV_FILE"
    sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASS}|"                     "$ENV_FILE"
    sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET}|"                     "$ENV_FILE"
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://caderno_app:${APP_DB_PASS}@postgres:5432/caderno|" "$ENV_FILE"
    sed -i "s|^TEST_DATABASE_URL=.*|TEST_DATABASE_URL=postgresql+asyncpg://caderno_app:${APP_DB_PASS}@postgres:5432/caderno_test|" "$ENV_FILE"
    sed -i "s|^REDIS_URL=.*|REDIS_URL=redis://:${REDIS_PASS}@redis:6379/0|"         "$ENV_FILE"

    for key in TOTP_ENCRYPTION_KEY FIELD_ENCRYPTION_KEY ATTACHMENT_MASTER_KEY IDENT_FIELD_KEY IDENT_INDEX_KEY; do
        value="$(gen_fernet)"
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    done

    chmod 600 "$ENV_FILE"
    info ".env criado (600)."
else
    info ".env já existe — mantido."
fi

if grep -q "GENERATE_ME" "$ENV_FILE"; then
    error "Sobraram valores GENERATE_ME no .env:"
    grep -n "GENERATE_ME" "$ENV_FILE" >&2
    exit 1
fi

# ── Build ────────────────────────────────────────────────────
info "A construir a imagem da API..."
$COMPOSE build api

info "A construir o frontend para o volume que o nginx serve..."
$COMPOSE --profile build run --rm frontend-build

# ── Database + migrations, before anything serves traffic ────
info "A arrancar a base de dados..."
$COMPOSE up -d --wait postgres redis

info "A aplicar migrações (alembic upgrade head)..."
$COMPOSE run --rm --no-deps api alembic upgrade head

# ── Up ───────────────────────────────────────────────────────
info "A subir a stack..."
$COMPOSE up -d --wait

echo
info "Pronto. Falta expor na tailnet (uma vez):"
echo "    sudo tailscale serve --bg 8090"
echo
info "Depois: https://\$(tailscale status --json | grep -o '\"DNSName\":\"[^\"]*' | head -1 | cut -d'\"' -f4)"
echo
info "Primeiro utilizador:"
echo "    CADERNO_SEED_PASSWORD='...' $COMPOSE run --rm api \\"
echo "        python -m scripts.seed --equipa 'Posto X' --codigo PX \\"
echo "        --username joao --nome 'João' --nip 1234567 --email joao@example.pt"
