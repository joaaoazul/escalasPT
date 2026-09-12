#!/usr/bin/env bash
# ============================================================
# EscalasPT — Production deployment script
# Usage:  bash deploy/setup.sh          (first run / update)
#         bash deploy/setup.sh --reset  (nuke everything, start fresh)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env.prod"
ENV_EXAMPLE="$SCRIPT_DIR/.env.prod.example"
COMPOSE="docker compose -f $SCRIPT_DIR/docker-compose.prod.yml --env-file $ENV_FILE"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Pre-flight checks ────────────────────────────────────────
command -v docker >/dev/null 2>&1 || { error "Docker not installed"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { error "Docker Compose (v2) not installed"; exit 1; }

# The compose file declares `web` as external, so it has to exist before `up`
# or the whole stack refuses to start. It is the network the shared Caddy uses
# to reach escalaspt-nginx by name.
if ! docker network inspect web >/dev/null 2>&1; then
    info "Creating the shared 'web' network..."
    docker network create web >/dev/null
fi

# ── Reset mode ────────────────────────────────────────────────
if [[ "${1:-}" == "--reset" ]]; then
    warn "RESET MODE: This will destroy ALL data (database, redis, frontend build)."
    read -rp "Are you sure? Type 'yes' to confirm: " RESET_CONFIRM
    if [[ "$RESET_CONFIRM" != "yes" ]]; then
        info "Aborted."
        exit 0
    fi
    info "Stopping containers and removing volumes..."
    docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" down -v 2>/dev/null || true
    # Also try with env-file in case it exists
    if [[ -f "$ENV_FILE" ]]; then
        docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" --env-file "$ENV_FILE" down -v 2>/dev/null || true
    fi
    info "Removing .env.prod..."
    rm -f "$ENV_FILE"
    info "Reset complete. Re-running setup..."
    echo ""
fi

# ── Generate .env.prod if missing ─────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    info "Generating .env.prod with random secrets..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"

    # Generate URL-safe passwords (hex only: 0-9a-f, no special chars)
    PG_PASS=$(openssl rand -hex 24)
    APP_DB_PASS=$(openssl rand -hex 24)
    REDIS_PASS=$(openssl rand -hex 16)
    JWT_SECRET=$(openssl rand -hex 32)

    # Generate Fernet key for TOTP encryption
    TOTP_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")

    # Replace placeholders
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" "$ENV_FILE"
    sed -i "s|^APP_DB_PASSWORD=.*|APP_DB_PASSWORD=${APP_DB_PASS}|" "$ENV_FILE"
    sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASS}|" "$ENV_FILE"
    sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET}|" "$ENV_FILE"
    if [[ -n "$TOTP_KEY" ]]; then
        sed -i "s|^TOTP_ENCRYPTION_KEY=.*|TOTP_ENCRYPTION_KEY=${TOTP_KEY}|" "$ENV_FILE"
    else
        warn "Could not generate TOTP key (python3 + cryptography needed). Set it manually."
    fi

    # Verify no GENERATE_ME placeholders remain
    if grep -q "GENERATE_ME" "$ENV_FILE"; then
        error "Failed to replace all placeholders in .env.prod!"
        grep "GENERATE_ME" "$ENV_FILE"
        exit 1
    fi

    warn "Review the generated .env.prod:"
    echo ""
    echo "─────────────────── .env.prod ───────────────────"
    cat "$ENV_FILE"
    echo "─────────────────────────────────────────────────"
    echo ""
    warn "Edit CORS_ORIGINS if your domain is not escalas.joaoazul.dev"
    echo ""
    read -rp "Continue with these values? [Y/n]: " CONFIRM
    if [[ "${CONFIRM,,}" == "n" ]]; then
        info "Edit the file: nano $ENV_FILE"
        info "Then re-run: bash deploy/setup.sh"
        exit 0
    fi
else
    info ".env.prod already exists, using existing values"
fi

# ── Validate env file ────────────────────────────────────────
info "Validating .env.prod..."
for VAR in POSTGRES_PASSWORD APP_DB_PASSWORD REDIS_PASSWORD JWT_SECRET_KEY; do
    VAL=$(grep "^${VAR}=" "$ENV_FILE" | cut -d'=' -f2-)
    if [[ -z "$VAL" || "$VAL" == "GENERATE_ME" ]]; then
        error "${VAR} is not set in .env.prod!"
        exit 1
    fi
done
info "Validation passed"

# ── Build and start ───────────────────────────────────────────
info "Building and starting containers..."
cd "$PROJECT_DIR"
$COMPOSE up -d --build

# ── Wait for API health ──────────────────────────────────────
info "Waiting for API to be healthy (up to 60s)..."
for i in $(seq 1 30); do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' escalaspt-api 2>/dev/null || echo "not found")
    if [[ "$STATUS" == "healthy" ]]; then
        info "API is healthy!"
        break
    fi
    if [[ $i -eq 30 ]]; then
        error "API did not become healthy. Status: $STATUS"
        error "Last 30 lines of API logs:"
        docker logs escalaspt-api --tail 30
        exit 1
    fi
    sleep 2
done

# ── Run migrations ────────────────────────────────────────────
info "Running database migrations..."
docker exec escalaspt-api alembic upgrade head

# ── Seed (optional) ──────────────────────────────────────────
read -rp "Run database seed? (first-time setup only) [y/N]: " SEED_ANSWER
if [[ "${SEED_ANSWER,,}" == "y" ]]; then
    info "Seed requires passwords for initial users."
    read -rsp "Admin password (min 8 chars, upper+lower+digit+special): " SEED_ADMIN_PW
    echo ""
    read -rsp "Commander password: " SEED_CMDT_PW
    echo ""
    read -rsp "Default military password: " SEED_DEFAULT_PW
    echo ""
    info "Seeding database..."
    docker exec -e SEED_ADMIN_PASSWORD="$SEED_ADMIN_PW" \
                -e SEED_CMDT_PASSWORD="$SEED_CMDT_PW" \
                -e SEED_DEFAULT_PASSWORD="$SEED_DEFAULT_PW" \
                escalaspt-api python -m scripts.seed
    info "Seed complete"
fi

# ── Summary ───────────────────────────────────────────────────
PORT=$(grep -oP 'ESCALASPT_PORT=\K.*' "$ENV_FILE" 2>/dev/null || echo "8443")
echo ""
info "========================================="
info " EscalasPT deployed successfully!"
info "========================================="
info " Internal:  http://localhost:${PORT}"
info ""
info " Next steps (TLS is handled by the Caddy already on this host):"
info "   1. Point escalas.joaoazul.dev at this server's IP"
info "   2. Paste deploy/Caddyfile's site block into that Caddy's Caddyfile"
info "   3. Put its Caddy service on the same network: docker network connect web <caddy-container>"
info "   4. Reload it: docker exec <caddy-container> caddy reload --config /etc/caddy/Caddyfile"
info "   5. Check CORS_ORIGINS in .env.prod matches the https:// domain"
info "   6. If you changed it: docker restart escalaspt-api"
info "========================================="
