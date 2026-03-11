#!/usr/bin/env bash
# restore-db.sh — Restore PostgreSQL + Qdrant from backup
# Usage: ./infra/scripts/restore-db.sh <backup_file.tar.gz>
set -euo pipefail

BACKUP_FILE="${1:-}"
RESTORE_TMP="/tmp/rag_restore_$$"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[restore]${NC} $*"; }
warn() { echo -e "${YELLOW}[restore]${NC} $*"; }
err()  { echo -e "${RED}[restore]${NC} $*" >&2; }

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    err "Usage: $0 <backup_file.tar.gz>"
    err "Available backups:"
    ls ./data/backups/rag_backup_*.tar.gz 2>/dev/null || echo "  (none found)"
    exit 1
fi

# Load env vars
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

POSTGRES_USER="${POSTGRES_USER:-raguser}"
POSTGRES_DB="${POSTGRES_DB:-ragdb}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-rag_postgres}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"

warn "⚠  This will OVERWRITE the current database!"
warn "   Backup file: ${BACKUP_FILE}"
read -p "   Type 'yes' to continue: " confirm
if [ "$confirm" != "yes" ]; then
    log "Restore cancelled."
    exit 0
fi

# ─── Extract Backup ───────────────────────────────────────────────────────────
mkdir -p "${RESTORE_TMP}"
log "Extracting backup..."
tar -xzf "${BACKUP_FILE}" -C "${RESTORE_TMP}"

# Find extracted directory
EXTRACT_DIR=$(ls -d "${RESTORE_TMP}"/*/  2>/dev/null | head -1)
if [ -z "$EXTRACT_DIR" ]; then
    err "Cannot find extracted backup contents."
    rm -rf "${RESTORE_TMP}"
    exit 1
fi

# ─── Restore PostgreSQL ───────────────────────────────────────────────────────
PG_DUMP=$(ls "${EXTRACT_DIR}"postgres_*.dump 2>/dev/null | head -1)
if [ -n "$PG_DUMP" ]; then
    log "Restoring PostgreSQL from: $(basename $PG_DUMP)"

    # Drop and recreate database
    docker exec "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${POSTGRES_DB}' AND pid <> pg_backend_pid();" \
        postgres > /dev/null 2>&1 || true

    docker exec "${POSTGRES_CONTAINER}" dropdb -U "${POSTGRES_USER}" --if-exists "${POSTGRES_DB}"
    docker exec "${POSTGRES_CONTAINER}" createdb -U "${POSTGRES_USER}" "${POSTGRES_DB}"

    # Restore dump
    docker cp "${PG_DUMP}" "${POSTGRES_CONTAINER}:/tmp/restore.dump"
    docker exec "${POSTGRES_CONTAINER}" pg_restore \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        --no-acl \
        --no-owner \
        /tmp/restore.dump
    docker exec "${POSTGRES_CONTAINER}" rm /tmp/restore.dump

    log "PostgreSQL restore complete."
else
    warn "No PostgreSQL dump found in backup."
fi

# ─── Restore Qdrant ───────────────────────────────────────────────────────────
QDRANT_SNAP=$(ls "${EXTRACT_DIR}"qdrant_*.snapshot 2>/dev/null | head -1)
if [ -n "$QDRANT_SNAP" ]; then
    log "Restoring Qdrant snapshot: $(basename $QDRANT_SNAP)"
    SNAP_NAME=$(basename "$QDRANT_SNAP")
    curl -sf -X POST "${QDRANT_URL}/snapshots/recover" \
        -H "Content-Type: application/json" \
        -d "{\"location\": \"file://${QDRANT_SNAP}\"}" > /dev/null
    log "Qdrant restore initiated."
else
    warn "No Qdrant snapshot found in backup."
fi

# ─── Cleanup ──────────────────────────────────────────────────────────────────
rm -rf "${RESTORE_TMP}"
log "Restore complete!"
