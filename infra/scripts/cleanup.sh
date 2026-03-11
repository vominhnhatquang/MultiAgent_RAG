#!/usr/bin/env bash
# cleanup.sh — Remove temp files, dangling images, and old logs
# Usage: ./infra/scripts/cleanup.sh [--full]
set -euo pipefail

FULL="${1:-}"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[cleanup]${NC} $*"; }
warn() { echo -e "${YELLOW}[cleanup]${NC} $*"; }

# ─── Docker cleanup ───────────────────────────────────────────────────────────
log "Removing stopped containers..."
docker container prune -f

log "Removing dangling images..."
docker image prune -f

log "Removing unused networks..."
docker network prune -f

if [ "$FULL" = "--full" ]; then
    warn "Full cleanup: removing unused volumes too!"
    docker volume prune -f
    log "Removing build cache..."
    docker builder prune -f
fi

# ─── Log cleanup ──────────────────────────────────────────────────────────────
log "Truncating large container logs..."
for container in rag_backend rag_frontend rag_postgres rag_qdrant rag_redis rag_ollama rag_celery; do
    LOG_FILE=$(docker inspect --format='{{.LogPath}}' "$container" 2>/dev/null || echo "")
    if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
        LOG_SIZE=$(du -sh "$LOG_FILE" | cut -f1)
        truncate -s 0 "$LOG_FILE" 2>/dev/null || true
        log "  Cleared log for ${container} (was ${LOG_SIZE})"
    fi
done

# ─── Temp files ───────────────────────────────────────────────────────────────
log "Removing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

log "Removing Next.js cache..."
rm -rf ./frontend/.next/cache 2>/dev/null || true

log "Removing temp files..."
find /tmp -name "rag_*" -mtime +1 -delete 2>/dev/null || true

# ─── Summary ──────────────────────────────────────────────────────────────────
log "Disk usage after cleanup:"
df -h . 2>/dev/null | tail -1
docker system df 2>/dev/null || true

log "Cleanup complete!"
