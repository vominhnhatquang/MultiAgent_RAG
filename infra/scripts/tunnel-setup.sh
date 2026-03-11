#!/usr/bin/env bash
# tunnel-setup.sh — Setup Cloudflare Tunnel (or ngrok fallback) for public access
# Usage: ./infra/scripts/tunnel-setup.sh [cloudflare|ngrok]
set -euo pipefail

TUNNEL_TYPE="${1:-cloudflare}"
SERVICE_PORT="${2:-3000}"  # Frontend port by default

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[tunnel]${NC} $*"; }
warn() { echo -e "${YELLOW}[tunnel]${NC} $*"; }
err()  { echo -e "${RED}[tunnel]${NC} $*" >&2; }

# Load env vars
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

setup_cloudflare() {
    log "Setting up Cloudflare Tunnel..."

    # Check if cloudflared is installed
    if ! command -v cloudflared &>/dev/null; then
        log "Installing cloudflared..."
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
                sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
            echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | \
                sudo tee /etc/apt/sources.list.d/cloudflared.list
            sudo apt-get update && sudo apt-get install -y cloudflared
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            brew install cloudflare/cloudflare/cloudflared
        else
            err "Unsupported OS. Install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/"
            exit 1
        fi
    fi

    # Check for tunnel token
    if [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
        log "Starting tunnel with token..."
        cloudflared tunnel --no-autoupdate run --token "${CLOUDFLARE_TUNNEL_TOKEN}"
    else
        # Quick tunnel (temporary, no account needed)
        warn "No CLOUDFLARE_TUNNEL_TOKEN set — creating temporary quick tunnel..."
        warn "For persistent tunnels, set CLOUDFLARE_TUNNEL_TOKEN in .env"
        cloudflared tunnel --no-autoupdate --url "http://localhost:${SERVICE_PORT}"
    fi
}

setup_ngrok() {
    log "Setting up ngrok tunnel..."

    if ! command -v ngrok &>/dev/null; then
        err "ngrok not installed. Download from https://ngrok.com/download"
        exit 1
    fi

    if [ -n "${NGROK_AUTHTOKEN:-}" ]; then
        ngrok config add-authtoken "${NGROK_AUTHTOKEN}"
    fi

    log "Starting ngrok on port ${SERVICE_PORT}..."
    ngrok http "${SERVICE_PORT}"
}

main() {
    case "$TUNNEL_TYPE" in
        cloudflare|cf)
            setup_cloudflare
            ;;
        ngrok)
            setup_ngrok
            ;;
        *)
            err "Unknown tunnel type: ${TUNNEL_TYPE}. Use 'cloudflare' or 'ngrok'."
            exit 1
            ;;
    esac
}

main "$@"
