#!/usr/bin/env bash
# ============================================================
# EscalasPT — Production deployment script
# Run on the VPS: bash deploy/setup.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env.prod"
ENV_EXAMPLE="$SCRIPT_DIR/.env.prod.example"

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

# ── Generate .env.prod if missing ─────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    info "Generating .env.prod with random secrets..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"

    PG_PASS=$(openssl rand -base64 24)
    REDIS_PASS=$(openssl rand -base64 24)
    JWT_SECRET=$(openssl rand -base64 32)
    # Generate Fernet key for TOTP encryption
    TOTP_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")

    # Replace placeholders in .env.prod
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" "$ENV_FILE"
    sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASS}|" "$ENV_FILE"
    sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET}|" "$ENV_FILE"
    if [[ -n "$TOTP_KEY" ]]; then
        sed -i "s|^TOTP_ENCRYPTION_KEY=.*|TOTP_ENCRYPTION_KEY=${TOTP_KEY}|" "$ENV_FILE"
    else
        warn "Could not generate TOTP key (cryptography package missing). Set it manually."
    fi

    warn "Edit .env.prod to set your DuckDNS domain in CORS_ORIGINS"
    warn "File: $ENV_FILE"
    echo ""
    read -rp "Press Enter after reviewing .env.prod, or Ctrl+C to abort..."
else
    info ".env.prod already exists, skipping generation"
fi

# ── Build and start ───────────────────────────────────────────
info "Building and starting containers..."
cd "$PROJECT_DIR"
docker compose -f deploy/docker-compose.prod.yml --env-file .env.prod up -d --build

# ── Wait for API health ──────────────────────────────────────
info "Waiting for API to be healthy..."
for i in $(seq 1 30); do
    if docker inspect --format='{{.State.Health.Status}}' escalaspt-api 2>/dev/null | grep -q healthy; then
        info "API is healthy!"
        break
    fi
    if [[ $i -eq 30 ]]; then
        error "API did not become healthy after 30 attempts"
        docker logs escalaspt-api --tail 50
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
info " Next steps:"
info "   1. Set up DuckDNS subdomain pointing to this server's IP"
info "   2. Install Caddy: sudo apt install caddy"
info "   3. Copy deploy/Caddyfile to /etc/caddy/Caddyfile"
info "   4. Replace YOURDOMAIN with your DuckDNS subdomain"
info "   5. sudo systemctl restart caddy"
info "   6. Update CORS_ORIGINS in .env.prod with your https:// domain"
info "   7. Restart API: docker restart escalaspt-api"
info "========================================="
