# Memory Budget - 10GB RAM Allocation
## RAM Management Strategy

**Author:** Alpha (System Architect)
**Version:** 1.1
**Updated:** 2026-03-20 — Reconciled with deployed docker-compose (Celery 500m, Ollama 6100m, concurrency=1)
**Hard Limit:** 10.0GB | **Usable:** 9.5GB | **Headroom:** 0.5GB

---

## 1. RAM Allocation Table

### 1.1 Base Allocation (Phase 1 - MVP)

| Service | RAM Limit | Details | docker-compose limit |
|---------|-----------|---------|---------------------|
| **Ollama** | **2.2 GB** | nomic (0.3) + gemma-2-2b-it (1.6) + overhead (0.3) | `mem_limit: 6100m` |
| PostgreSQL | 0.8 GB | shared_buffers=256MB, work_mem=4MB | `mem_limit: 800m` |
| Qdrant | 0.8 GB | HNSW cache + disk storage | `mem_limit: 800m` |
| Backend (FastAPI) | 0.5 GB | 2 Uvicorn workers | `mem_limit: 700m` |
| Frontend (Next.js) | 0.2 GB | SSR runtime | `mem_limit: 200m` |
| OS + Buffer | 1.1 GB | Kernel, filesystem cache, spikes | - |
| **Phase 1 Total** | **5.6 GB** | | |

### 1.2 Phase 2 Addition (Intelligence)

| Service | RAM Change | New Total | Notes |
|---------|-----------|-----------|-------|
| Ollama | +0.4 GB (reranker) | **2.6 GB** | bge-reranker-v2 always loaded |
| Redis | +0.3 GB (new) | **0.3 GB** | Hot session cache, Celery broker |
| Celery Worker | +0.5 GB (new) | **0.5 GB** | 1 worker, concurrency=1 |
| Celery Beat | +0.1 GB (new) | **0.1 GB** | Periodic task scheduler |
| **Phase 2 Total** | | **6.9 GB** | |

### 1.3 Phase 3 - Full Load (Normal Operation)

| Service | RAM Limit | % of Total |
|---------|-----------|------------|
| **Ollama** | **2.6 GB** | 26% |
| - nomic-embed-text | 0.3 GB | |
| - gemma-2-2b-it (Q8_0 GGUF) | 1.6 GB | |
| - bge-reranker-v2 | 0.4 GB | |
| - overhead | 0.3 GB | |
| PostgreSQL | 0.8 GB | 8% |
| Qdrant | 0.8 GB | 8% |
| Redis | 0.3 GB | 3% |
| Backend (FastAPI) | 0.5 GB | 5% |
| Frontend (Next.js) | 0.2 GB | 2% |
| Celery Worker | 0.5 GB | 5% |
| Celery Beat | 0.1 GB | 1% |
| OS + Buffer | 1.1 GB | 11% |
| **SUBTOTAL (Normal)** | **6.9 GB** | 69% |
| **Headroom for spikes** | **3.1 GB** | 31% |

### 1.4 Phase 3 - Peak Load (llama3.1 Swap)

| Service | RAM During Swap | Notes |
|---------|----------------|-------|
| **Ollama** | **5.7 GB** | nomic (0.3) + llama3.1 (4.7) + reranker (0.4) + overhead (0.3) |
| PostgreSQL | 0.8 GB | |
| Qdrant | 0.8 GB | |
| Redis | 0.3 GB | |
| Backend | 0.5 GB | |
| Frontend | 0.2 GB | |
| Celery | 0.5 GB | |
| Celery Beat | 0.1 GB | |
| OS + Buffer | 0.8 GB | Reduced during swap |
| **PEAK TOTAL** | **9.7 GB** | 0.3GB headroom |

---

## 2. Ollama Memory Management

### 2.1 Model Inventory

| Model | Size | Load Time | Phase | Status |
|-------|------|-----------|-------|--------|
| nomic-embed-text | 0.3 GB | < 2s | 1+ | Always loaded |
| gemma-2-2b-it (Q8_0 GGUF) | 1.6 GB | < 5s | 1+ | Default loaded |
| bge-reranker-v2 | 0.4 GB | < 3s | 2+ | Always loaded |
| llama3.1:8b | 4.7 GB | ~15s | 3 | On-demand SWAP |

### 2.2 Swap Strategy

```
NORMAL STATE (6.9GB total):
  Ollama: nomic(0.3) + gemma-2-2b-it(1.6) + reranker(0.4) = 2.3GB loaded

SWAP SEQUENCE (khi can llama3.1):
  1. Block new requests (queue them)
  2. Unload gemma-2-2b-it    -> Free 1.6GB -> Ollama = 0.7GB
  3. Load llama3.1:8b        -> Alloc 4.7GB -> Ollama = 5.4GB
  4. Generate response        -> ~30s
  5. Unload llama3.1:8b      -> Free 4.7GB -> Ollama = 0.7GB
  6. Load gemma-2-2b-it      -> Alloc 1.6GB -> Ollama = 2.3GB
  7. Unblock requests

  Peak during swap: 5.4GB Ollama + 4.3GB others = 9.7GB
  TIGHT: 0.3GB headroom
```

### 2.3 Ollama Docker Config

```yaml
ollama:
  image: ollama/ollama:latest
  mem_limit: 6100m
  memswap_limit: 6100m
  environment:
    - OLLAMA_NUM_PARALLEL=2       # Max concurrent requests
    - OLLAMA_MAX_LOADED_MODELS=3  # nomic + gemma-2-2b-it/llama + reranker
    - OLLAMA_KEEP_ALIVE=5m        # Unload idle models after 5min
```

---

## 3. PostgreSQL Memory Config

```
# postgresql.conf optimized for 0.8GB limit

shared_buffers = 256MB          # 32% of limit
effective_cache_size = 512MB    # Hint to planner
work_mem = 4MB                  # Per-sort operation
maintenance_work_mem = 64MB     # For VACUUM, CREATE INDEX
wal_buffers = 8MB
max_connections = 20            # Limited for RAM
checkpoint_completion_target = 0.9

# pgvector specific
max_parallel_workers_per_gather = 2
```

---

## 4. Qdrant Memory Config

```yaml
# qdrant config
storage:
  on_disk_payload: true         # Payloads on disk, not RAM
  performance:
    max_search_threads: 2

optimizers:
  memmap_threshold_kb: 20000    # Use mmap after 20MB
  indexing_threshold_kb: 10000

service:
  max_request_size_mb: 10
```

---

## 5. Redis Memory Config

```conf
# redis.conf
maxmemory 300mb
maxmemory-policy allkeys-lru    # Evict least recently used
save ""                          # Disable RDB persistence (use AOF)
appendonly yes
appendfsync everysec
```

---

## 6. Concurrent Session Impact

### 6.1 RAM per Active Session

| Component | RAM per Session | Source |
|-----------|----------------|--------|
| Redis cache | ~5 KB | 3 turns x ~1.5KB |
| Backend state | ~2 KB | In-memory request context |
| SSE connection | ~1 KB | HTTP keep-alive |
| **Total per session** | **~8 KB** | Negligible |

### 6.2 Bottleneck: Ollama Inference

```
gemma-2-2b-it concurrent performance:
  - 1 request:  ~2s first token, 15 tok/s
  - 3 requests: ~4s first token, 8 tok/s each
  - 5 requests: ~8s first token, 5 tok/s each
  - 10 requests: ~15s first token (degraded)

Recommendation: OLLAMA_NUM_PARALLEL=2, queue the rest
Max concurrent sessions: 10 (queue beyond 2 active inference)
```

### 6.3 Stress Test Scenarios

| Scenario | Expected RAM | Status |
|----------|-------------|--------|
| Idle (no sessions) | ~4.4 GB | OK |
| 1 active chat (gemma-2-2b-it) | ~6.9 GB | OK |
| 5 active chats (gemma-2-2b-it) | ~7.0 GB | OK |
| 1 swap to llama3.1 | ~9.4 GB | WARNING (0.6 headroom) |
| 5 chats + 1 swap | ~9.6 GB | CRITICAL |
| Document ingestion (100 chunks) | ~7.3 GB | OK |
| Ingestion + 3 chats | ~7.5 GB | OK |
| Ingestion + swap | ~9.7 GB | CRITICAL (0.3 headroom) |

---

## 7. OOM Prevention Rules

1. **Never load gemma-2-2b-it + llama3.1 simultaneously** (1.6+4.7=6.3GB, exceeds Ollama budget with other models)
2. **Block new requests during model swap** (15-20s queue is acceptable)
3. **Limit concurrent Ollama inference to 2** (OLLAMA_NUM_PARALLEL=2)
4. **Monitor with docker stats** - alert at 9.0GB
5. **Redis eviction policy: allkeys-lru** - auto-free when hitting 300MB
6. **PostgreSQL max_connections: 20** - prevent connection explosion
7. **Celery worker concurrency: 1** - limit parallel ingestion (increased from 200MB to 500MB to avoid OOM)

---

## 8. Memory Monitoring

### 8.1 Health Check Endpoint Response

```json
{
  "status": "healthy",
  "memory": {
    "total_gb": 10.0,
    "used_gb": 6.8,
    "available_gb": 3.2,
    "services": {
      "ollama": {"used_mb": 2400, "limit_mb": 6100, "models_loaded": ["nomic", "gemma-2-2b-it", "reranker"]},
      "postgres": {"used_mb": 650, "limit_mb": 800},
      "qdrant": {"used_mb": 500, "limit_mb": 800},
      "redis": {"used_mb": 45, "limit_mb": 300},
      "backend": {"used_mb": 280, "limit_mb": 500},
      "frontend": {"used_mb": 180, "limit_mb": 300}
    }
  },
  "warnings": []
}
```

### 8.2 Alert Thresholds

| Level | Total RAM Used | Action |
|-------|---------------|--------|
| Normal | < 8.0 GB | No action |
| Warning | 8.0 - 9.0 GB | Log warning, consider unloading idle models |
| Critical | 9.0 - 9.5 GB | Block new sessions, queue requests |
| Emergency | > 9.5 GB | Force unload llama3.1, reject new connections |
