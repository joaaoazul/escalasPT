#!/usr/bin/env bash
# ============================================================
# Caderno de Serviço — instalar as cópias de segurança nocturnas
#
#   sudo bash deploy/install-backups.sh
#
# Gera o par de chaves, IMPRIME a chave privada uma única vez (para guardares
# fora do servidor) e instala um temporizador systemd diário.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${CADERNO_BACKUP_DIR:-/opt/caderno/backups}"
PUBKEY_FILE="$BACKUP_DIR/backup-key.pub"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $*"; }

[[ $EUID -eq 0 ]] || { echo "Correr com sudo." >&2; exit 1; }
command -v age >/dev/null || { echo "Falta o age — correr deploy/provision.sh." >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [[ ! -f "$PUBKEY_FILE" ]]; then
    info "A gerar o par de chaves das cópias..."
    TMPKEY="$(mktemp)"
    age-keygen -o "$TMPKEY" 2>/dev/null
    grep 'public key:' "$TMPKEY" | sed 's/.*public key: //' > "$PUBKEY_FILE"
    chmod 644 "$PUBKEY_FILE"

    echo
    warn "════════════════════════════════════════════════════════════"
    warn " CHAVE PRIVADA — aparece UMA vez. Sem ela não há restauro."
    warn " Guardar fora deste servidor (gestor de palavras-passe)."
    warn "════════════════════════════════════════════════════════════"
    echo
    grep 'AGE-SECRET-KEY' "$TMPKEY"
    echo
    read -rp "Escrever 'guardei' para continuar: " CONFIRMA
    [[ "$CONFIRMA" == "guardei" ]] || { rm -f "$TMPKEY" "$PUBKEY_FILE"; echo "Abortado."; exit 1; }
    shred -u "$TMPKEY" 2>/dev/null || rm -f "$TMPKEY"
    info "Chave privada apagada do servidor. Fica só a pública."
else
    info "Já existe chave pública em $PUBKEY_FILE — mantida."
fi

cat > /etc/systemd/system/caderno-backup.service <<UNIT
[Unit]
Description=Cópia de segurança do Caderno de Serviço
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash $APP_DIR/deploy/backup.sh
Environment=CADERNO_BACKUP_DIR=$BACKUP_DIR
UNIT

cat > /etc/systemd/system/caderno-backup.timer <<'UNIT'
[Unit]
Description=Cópia de segurança nocturna do Caderno de Serviço

[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=20m
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now caderno-backup.timer

info "A correr uma cópia agora, para provar que funciona..."
systemctl start caderno-backup.service
sleep 2
if [[ -f "$BACKUP_DIR/ESTADO.json" ]] && grep -q '"estado":"ok"' "$BACKUP_DIR/ESTADO.json"; then
    info "Primeira cópia feita: $(cat "$BACKUP_DIR/ESTADO.json")"
else
    warn "A primeira cópia não correu bem:"
    journalctl -u caderno-backup.service -n 20 --no-pager
    exit 1
fi

echo
info "Temporizador activo. Próxima: $(systemctl list-timers caderno-backup.timer --no-pager | sed -n 2p)"
