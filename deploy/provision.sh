#!/usr/bin/env bash
# ============================================================
# Caderno de Serviço — preparar um servidor limpo
#
#   sudo bash deploy/provision.sh            fecha o porto 22 à internet
#   sudo bash deploy/provision.sh --keep-ssh mantém o 22 aberto
#
# Instala o que a app precisa e mais nada: Docker, Tailscale, firewall,
# actualizações automáticas, swap. NÃO instala nginx nem certbot no anfitrião —
# o nginx corre em contentor e o TLS é do `tailscale serve`.
#
# Idempotente: correr duas vezes não faz mal.
# Testado em Debian 12 e Ubuntu 22.04/24.04.
# ============================================================
set -euo pipefail

KEEP_SSH=false
[[ "${1:-}" == "--keep-ssh" ]] && KEEP_SSH=true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[AVISO]${NC} $*"; }
error() { echo -e "${RED}[ERRO]${NC} $*" >&2; }

[[ $EUID -eq 0 ]] || { error "Correr com sudo."; exit 1; }
command -v apt-get >/dev/null || { error "Este script é para Debian/Ubuntu."; exit 1; }

# shellcheck disable=SC1091
. /etc/os-release
info "Sistema: $PRETTY_NAME"

APP_USER="${SUDO_USER:-caderno}"
APP_DIR="/opt/caderno"

export DEBIAN_FRONTEND=noninteractive

# ── Base ─────────────────────────────────────────────────────
info "A instalar pacotes base..."
apt-get update -qq
apt-get install -y -qq \
    ca-certificates curl gnupg git openssl \
    ufw unattended-upgrades chrony \
    python3 python3-venv gzip

# Cifra das cópias de segurança. Em algumas imagens está no universe/backports;
# se faltar, o servidor fica preparado na mesma e o install-backups.sh avisa.
apt-get install -y -qq age || warn "O 'age' não está disponível nos repositórios — instalar antes de deploy/install-backups.sh."

timedatectl set-timezone Europe/Lisbon || warn "Não consegui definir o fuso horário."

# ── Swap (Postgres + build do frontend num servidor pequeno) ──
MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [[ $MEM_MB -lt 4096 ]] && ! swapon --show | grep -q .; then
    info "RAM = ${MEM_MB}MB e sem swap — a criar 2GB em /swapfile."
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
    chmod 600 /swapfile
    mkswap -q /swapfile
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -qw vm.swappiness=10
    grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# ── Docker (repositório oficial, não o docker.io da distro) ──
if ! command -v docker >/dev/null; then
    info "A instalar o Docker Engine..."
    install -m 0755 -d /etc/apt/keyrings
    DOCKER_DISTRO=$([[ "$ID" == "ubuntu" ]] && echo ubuntu || echo debian)
    curl -fsSL "https://download.docker.com/linux/${DOCKER_DISTRO}/gpg" \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] " \
         "https://download.docker.com/linux/${DOCKER_DISTRO} ${VERSION_CODENAME} stable" \
        | tr -s ' ' > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
else
    info "Docker já instalado: $(docker --version)"
fi

# Sem isto, um contentor com um ciclo de erros enche o disco em dias.
if [[ ! -f /etc/docker/daemon.json ]]; then
    info "A limitar os logs do Docker..."
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "5" },
  "live-restore": true
}
JSON
    systemctl restart docker
fi

systemctl enable --now docker >/dev/null
if [[ "$APP_USER" != "root" ]]; then
    id -nG "$APP_USER" | grep -qw docker || {
        usermod -aG docker "$APP_USER"
        warn "$APP_USER foi adicionado ao grupo docker — é preciso voltar a entrar."
    }
fi

# ── Tailscale ────────────────────────────────────────────────
if ! command -v tailscale >/dev/null; then
    info "A instalar o Tailscale..."
    curl -fsSL "https://pkgs.tailscale.com/stable/${ID}/${VERSION_CODENAME}.noarmor.gpg" \
        > /usr/share/keyrings/tailscale-archive-keyring.gpg
    curl -fsSL "https://pkgs.tailscale.com/stable/${ID}/${VERSION_CODENAME}.tailscale-keyring.list" \
        > /etc/apt/sources.list.d/tailscale.list
    apt-get update -qq
    apt-get install -y -qq tailscale
    systemctl enable --now tailscaled >/dev/null
else
    info "Tailscale já instalado: $(tailscale version | head -1)"
fi

# ── Firewall ─────────────────────────────────────────────────
# O compose publica em 127.0.0.1:8090, portanto nada da app fica exposto. Isto é
# a segunda linha: mesmo que um dia alguém publique em 0.0.0.0 por distracção,
# a porta continua fechada de fora.
#
# Atenção: o Docker escreve directamente no iptables e passa ao lado do ufw
# quando se publica em 0.0.0.0 — a regra que protege de facto é publicar só em
# 127.0.0.1, como o docker-compose.yml faz.
info "A configurar o firewall..."
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow in on tailscale0 >/dev/null          # tudo o que vem da tailnet
ufw allow 41641/udp >/dev/null                  # ligação directa do Tailscale

if $KEEP_SSH; then
    ufw allow 22/tcp >/dev/null
    warn "Porto 22 aberto à internet (--keep-ssh)."
else
    info "Porto 22 fechado à internet — o SSH passa a ser pela tailnet."
    warn "Confirma que consegues entrar por Tailscale ANTES de sair desta sessão."
fi
ufw --force enable >/dev/null

# ── Actualizações de segurança automáticas ───────────────────
info "A ligar as actualizações de segurança..."
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
CONF
cat > /etc/apt/apt.conf.d/51caderno-unattended <<'CONF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "05:30";
CONF
systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true

# ── Sítio da app ─────────────────────────────────────────────
mkdir -p "$APP_DIR" "$APP_DIR/backups"
chown -R "$APP_USER:$APP_USER" "$APP_DIR" 2>/dev/null || true
chmod 700 "$APP_DIR/backups"

echo
info "Servidor preparado. A seguir:"
cat <<NEXT

  1. Ligar à tailnet (abre um link para autenticar):
       sudo tailscale up --ssh

  2. Clonar e subir a app:
       git clone <repo> $APP_DIR/app && cd $APP_DIR/app
       bash deploy/setup.sh

  3. Publicar na tailnet:
       sudo tailscale serve --bg 8090
       tailscale serve status

  4. Primeiro utilizador:
       ver deploy/SERVIDOR.md §6

  5. Cópias de segurança:
       sudo bash deploy/install-backups.sh

NEXT
