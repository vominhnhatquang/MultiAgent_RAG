#!/usr/bin/env bash
# health-check.sh — Check all services + RAM usage per process
# Usage: ./infra/scripts/health-check.sh [--wait]
set -uo pipefail

# If --wait flag: give slow-starting containers time to become healthy
if [[ "${1:-}" == "--wait" ]]; then
    echo "Waiting 30s for all services to stabilize..."
    sleep 30
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0

ok()   { echo -e "  ${GREEN}✓${NC} $*"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}✗${NC} $*"; FAIL=$((FAIL + 1)); }
info() { echo -e "${CYAN}[health-check]${NC} $*"; }

check_http() {
    local name="$1" url="$2"
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        ok "$name — $url"
    else
        fail "$name — $url (unreachable)"
    fi
}

check_tcp() {
    local name="$1" host="$2" port="$3"
    if timeout 3 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" 2>/dev/null; then
        ok "$name — ${host}:${port}"
    else
        fail "$name — ${host}:${port} (unreachable)"
    fi
}

check_docker_container() {
    local name="$1" container="$2"
    if docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null | grep -q "healthy"; then
        ok "$name container — healthy"
    elif docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null | grep -q "running"; then
        ok "$name container — running (no healthcheck)"
    else
        fail "$name container — not running"
    fi
}

check_ram_usage() {
    info "=== RAM Usage per Container ==="
    if command -v docker &>/dev/null; then
        docker stats --no-stream --format \
            "  {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null | \
            column -t -s $'\t' || echo "  (docker stats unavailable)"
    fi

    echo ""
    info "=== System RAM ==="
    free -h 2>/dev/null || cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree"

    # Warn if total > 9GB
    if command -v python3 &>/dev/null; then
        python3 -c "
import subprocess, re
try:
    result = subprocess.run(['free', '-m'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if line.startswith('Mem:'):
            parts = line.split()
            used = int(parts[2])
            total = int(parts[1])
            pct = used / total * 100
            color = '\033[0;31m' if used > 9216 else '\033[0;33m' if used > 8192 else '\033[0;32m'
            print(f'  {color}RAM used: {used}MB / {total}MB ({pct:.1f}%)\033[0m')
            if used > 9216:
                print('  \033[0;31m⚠ WARNING: RAM usage > 9GB — OOM risk!\033[0m')
except:
    pass
" 2>/dev/null
    fi
}

main() {
    echo ""
    info "=== RAG Chatbot Health Check — $(date) ==="
    echo ""

    info "=== HTTP Endpoints ==="
    check_http "Backend API"    "http://localhost:8000/health"
    check_http "Frontend"       "http://localhost:3000"
    check_http "Qdrant"         "http://localhost:6333/healthz"
    check_http "Ollama"         "http://localhost:11434/api/tags"

    echo ""
    info "=== TCP Connectivity ==="
    check_tcp "PostgreSQL"  "localhost" "5432"
    check_tcp "Redis"       "localhost" "6379"

    echo ""
    info "=== Docker Containers ==="
    check_docker_container "Backend"   "rag_backend"
    check_docker_container "Frontend"  "rag_frontend"
    check_docker_container "Postgres"  "rag_postgres"
    check_docker_container "Qdrant"    "rag_qdrant"
    check_docker_container "Redis"     "rag_redis"
    check_docker_container "Ollama"    "rag_ollama"
    check_docker_container "Celery"       "rag_celery"
    check_docker_container "Celery Beat"  "rag_celery_beat"

    echo ""
    check_ram_usage

    echo ""
    info "=== Summary ==="
    if [ $FAIL -eq 0 ]; then
        echo -e "  ${GREEN}All checks passed (${PASS}/${PASS})${NC}"
        exit 0
    else
        echo -e "  ${RED}${FAIL} check(s) failed, ${PASS} passed${NC}"
        exit 1
    fi
}

main "$@"
