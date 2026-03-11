#!/usr/bin/env bash
# backup-db.sh — Backup PostgreSQL + Qdrant
# Usage: ./infra/scripts/backup-db.sh [BACKUP_DIR]
set -euo pipefail

BACKUP_DIR="${1:-./data/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[backup]${NC} $*"; }
err() { echo -e "${RED}[backup]${NC} $*" >&2; }

# Load env vars
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

POSTGRES_USER="${POSTGRES_USER:-raguser}"
POSTGRES_DB="${POSTGRES_DB:-ragdb}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-rag_postgres}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"

mkdir -p "${BACKUP_PATH}"

# ─── PostgreSQL Backup ────────────────────────────────────────────────────────
log "Backing up PostgreSQL database: ${POSTGRES_DB}"
if docker exec "${POSTGRES_CONTAINER}" pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --no-acl \
    --no-owner \
    -Fc \
    > "${BACKUP_PATH}/postgres_${POSTGRES_DB}_${TIMESTAMP}.dump"; then
    log "PostgreSQL backup saved: ${BACKUP_PATH}/postgres_${POSTGRES_DB}_${TIMESTAMP}.dump"
else
    err "PostgreSQL backup failed!"
    exit 1
fi

# ─── Qdrant Snapshot ──────────────────────────────────────────────────────────
log "Creating Qdrant snapshot..."
SNAPSHOT_RESPONSE=$(curl -sf -X POST "${QDRANT_URL}/snapshots" \
    -H "Content-Type: application/json" 2>/dev/null || echo '{"status":"error"}')

SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('result', {}).get('name', ''))
" 2>/dev/null)

if [ -n "$SNAPSHOT_NAME" ]; then
    # Download snapshot
    curl -sf "${QDRANT_URL}/snapshots/${SNAPSHOT_NAME}" \
        -o "${BACKUP_PATH}/qdrant_${TIMESTAMP}.snapshot"
    log "Qdrant snapshot saved: ${BACKUP_PATH}/qdrant_${TIMESTAMP}.snapshot"
else
    log "Qdrant snapshot not available or empty collection — skipping."
fi

# ─── Compress Backup ──────────────────────────────────────────────────────────
log "Compressing backup..."
tar -czf "${BACKUP_DIR}/rag_backup_${TIMESTAMP}.tar.gz" -C "${BACKUP_DIR}" "${TIMESTAMP}"
rm -rf "${BACKUP_PATH}"

BACKUP_SIZE=$(du -sh "${BACKUP_DIR}/rag_backup_${TIMESTAMP}.tar.gz" | cut -f1)
log "Backup complete: ${BACKUP_DIR}/rag_backup_${TIMESTAMP}.tar.gz (${BACKUP_SIZE})"

# ─── Cleanup Old Backups (keep last 7) ────────────────────────────────────────
log "Cleaning old backups (keeping last 7)..."
ls -t "${BACKUP_DIR}"/rag_backup_*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
log "Done."
