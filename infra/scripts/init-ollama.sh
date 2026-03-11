#!/usr/bin/env bash
# init-ollama.sh — Verify/pull required Ollama models
# Usage: ./infra/scripts/init-ollama.sh [OLLAMA_URL]
set -euo pipefail

OLLAMA_URL="${1:-http://localhost:11434}"
TIMEOUT=300

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[init-ollama]${NC} $*"; }
warn() { echo -e "${YELLOW}[init-ollama]${NC} $*"; }
err()  { echo -e "${RED}[init-ollama]${NC} $*" >&2; }

wait_for_ollama() {
    log "Waiting for Ollama at ${OLLAMA_URL}..."
    local elapsed=0
    until curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; do
        if [ $elapsed -ge $TIMEOUT ]; then
            err "Ollama not ready after ${TIMEOUT}s."
            exit 1
        fi
        sleep 5; elapsed=$((elapsed + 5)); echo -n "."
    done
    echo ""; log "Ollama is ready!"
}

check_or_pull() {
    local model="$1"
    # Model name may contain "/" — grep for the short name after last "/"
    local short_name="${model##*/}"
    if curl -sf "${OLLAMA_URL}/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
names = [m['name'] for m in data.get('models', [])]
target = '${model}'
# Match exact or partial (HuggingFace models have full path)
found = any(target in n or n in target for n in names)
exit(0 if found else 1)
" 2>/dev/null; then
        log "  ✓ ${model} — already present"
    else
        warn "  ↓ ${model} — pulling..."
        curl -s -X POST "${OLLAMA_URL}/api/pull" \
            -H "Content-Type: application/json" \
            -d "{\"name\": \"${model}\"}" | while IFS= read -r line; do
            status=$(echo "$line" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('status',''))" 2>/dev/null || echo "")
            [ -n "$status" ] && echo -ne "\r    ${status}                    "
        done
        echo ""; log "  ✓ ${model} — pulled."
    fi
}

main() {
    wait_for_ollama

    log "=== Checking required models ==="

    # Embedding (always loaded, lightweight)
    check_or_pull "nomic-embed-text"

    # Reranker
    check_or_pull "hf.co/gpustack/bge-reranker-v2-m3-GGUF:Q8_0"

    # LLM lightweight (default chat model)
    check_or_pull "hf.co/MaziyarPanahi/gemma-2-2b-it-GGUF:Q8_0"

    # LLM heavy (swap strategy — unload gemma2 → load llama3.1)
    check_or_pull "hf.co/modularai/Llama-3.1-8B-Instruct-GGUF:Q4_K_M"

    log ""
    log "=== Available models ==="
    curl -sf "${OLLAMA_URL}/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
total = 0
for m in data.get('models', []):
    size_gb = m.get('size', 0) / (1024**3)
    total += size_gb
    print(f\"  {m['name']:<55} {size_gb:.2f} GB\")
print(f\"  {'─'*65}\")
print(f\"  Total on disk: {total:.2f} GB\")
"
    log "Ollama init complete — system ready for backend."
}

main "$@"
