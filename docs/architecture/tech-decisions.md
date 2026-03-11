# Architecture Decision Records (ADR)
## RAG Chatbot 10GB

**Author:** Alpha (System Architect)
**Version:** 1.0

---

## ADR-001: Vector Database - Qdrant (Separate) + pgvector (Backup)

**Status:** Accepted
**Date:** 2026-03-10

### Context
Can lua chon vector database cho semantic search tren 768-dim embeddings, trong gioi han 0.8GB RAM.

### Decision
Dung Qdrant lam primary vector DB, pgvector trong PostgreSQL lam backup/fallback.

### Alternatives Considered

| Option | Pros | Cons | RAM |
|--------|------|------|-----|
| **Qdrant (chosen)** | HNSW tuning, filtering, scalar quantization, REST API | Them 1 service | 0.8GB |
| pgvector only | Khong them service, cung PG | Search cham hon 5-10x voi >10k vectors, khong co quantization | 0 extra |
| ChromaDB | Python-native, don gian | Khong production-grade, RAM greedy | ~1GB |
| Weaviate | Feature-rich | Qua nang cho 10GB constraint | ~2GB |
| Milvus | Distributed | Overkill, can nhieu RAM | ~3GB |

### Trade-offs
- (+) Qdrant cho phep int8 quantization -> giam RAM 4x cho vectors
- (+) on_disk_payload=true -> chi giu vectors trong RAM, payload tren disk
- (+) pgvector lam fallback khi Qdrant down
- (-) Them 1 container can quan ly
- (-) Data duplication (vectors o ca 2 noi)

### Consequences
- Beta can implement dual-write (Qdrant + PG) khi indexing
- Beta can implement fallback logic khi Qdrant unavailable
- Epsilon can set memory limit 800m cho Qdrant container

---

## ADR-002: LLM Serving - Ollama voi Model Swap Strategy

**Status:** Accepted
**Date:** 2026-03-10

### Context
Can serving nhieu LLM models (embed, chat, rerank) trong gioi han 6.5GB total Ollama RAM.

### Decision
Dung Ollama voi swap strategy: chi 1 large LLM (gemma2 HOAC llama3.1) tai bat ky thoi diem nao.

### Model Selection

| Model | Size | Purpose | Load Strategy |
|-------|------|---------|---------------|
| nomic-embed-text | 0.3GB | Embedding 768-dim | Always loaded |
| gemma2:2b | 1.6GB | Default chat, HyDE, intent | Always loaded (default) |
| bge-reranker-v2 | 0.4GB | Cross-encoder rerank | Always loaded (Phase 2+) |
| llama3.1:8b | 4.7GB | Heavy offline queries | On-demand swap |

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Ollama (chosen)** | Simple API, model management, swap API | Overhead ~300MB |
| vLLM | Fast batching, PagedAttention | 2GB+ overhead, overkill |
| llama.cpp directly | Minimal overhead | No model management, manual load/unload |
| Text Generation Inference (TGI) | Production-grade | 1.5GB+ overhead |

### Trade-offs
- (+) Ollama API don gian (HTTP), Beta de integrate
- (+) Built-in model pull, list, load/unload
- (+) OLLAMA_KEEP_ALIVE=5m tu dong unload idle models
- (-) Swap time ~15-20s khi chuyen gemma2 <-> llama3.1
- (-) Block requests during swap

---

## ADR-003: Cloud LLM Fallback - Gemini API

**Status:** Accepted
**Date:** 2026-03-10

### Context
Can cloud LLM cho hard queries ma gemma2:2b khong xu ly tot, khong ton RAM local.

### Decision
Dung Google Gemini 2.5 Pro API (free tier: 15 RPM, 1M tokens/day).

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Gemini API (chosen)** | Free tier generous, fast, multi-language | Google dependency |
| OpenAI GPT-4o-mini | Established, good quality | Tra phi, no free tier |
| Claude API | Best reasoning | Tra phi, rate limit thap free |
| Groq (Llama hosted) | Ultra fast | Limited models, rate limit |

### Trade-offs
- (+) 0 RAM local, 15 requests/minute free
- (+) Tot cho Vietnamese language
- (-) Internet dependency
- (-) Latency ~1-2s (network)
- (-) Google co the thay doi free tier

### Routing Logic
```
Easy + Online  -> gemma2:2b (local, fast)
Hard + Online  -> Gemini API (cloud, smart)
Any  + Offline -> llama3.1:8b (local, swap)
```

---

## ADR-004: Hybrid Retrieval - BM25 + Vector + RRF

**Status:** Accepted
**Date:** 2026-03-10

### Context
Vector search alone misses keyword-exact matches; BM25 alone misses semantic similarity.

### Decision
Hybrid search: BM25 (PostgreSQL tsvector) + Vector (Qdrant) fused via Reciprocal Rank Fusion (RRF).

### Flow
```
Query -> embed -> Qdrant (top 10)  ─┐
Query -> tokenize -> PG BM25 (top 5) ─┤-> RRF merge -> top 20 -> Rerank -> top 5
```

### RRF Formula
```
score(d) = SUM( 1 / (k + rank_i(d)) ) for each retriever i
k = 60 (constant, standard value)
```

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Vector only | Don gian | Miss keyword matches |
| BM25 only | Fast, exact | Miss semantic meaning |
| **Hybrid RRF (chosen)** | Best of both | Them complexity, 2 searches |
| Weighted linear combination | Tunable | Can normalize scores, fragile |

### Trade-offs
- (+) Captures both exact keyword va semantic meaning
- (+) RRF khong can normalize scores (rank-based)
- (+) BM25 via PG GIN index -> no extra service
- (-) 2 parallel searches -> tang latency ~50ms
- (-) Can deduplicate results

---

## ADR-005: Streaming Response - SSE (not WebSocket)

**Status:** Accepted
**Date:** 2026-03-10

### Context
Can streaming LLM response token-by-token den client.

### Decision
Server-Sent Events (SSE) thay vi WebSocket.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **SSE (chosen)** | Simple, HTTP-native, auto-reconnect | Unidirectional only |
| WebSocket | Bidirectional, low latency | Complex setup, connection management |
| HTTP Long Polling | Simple | Wasteful, high latency |
| gRPC streaming | Efficient, typed | Overkill, frontend complexity |

### Trade-offs
- (+) SSE hoat dong tren HTTP/1.1 va HTTP/2
- (+) Browser native EventSource API
- (+) Auto-reconnect built-in
- (+) FastAPI ho tro SSE via StreamingResponse
- (-) Chi server -> client (du cho chat use case)
- (-) Max 6 connections per domain (HTTP/1.1)

---

## ADR-006: Memory Tiers - Hot/Warm/Cold

**Status:** Accepted (Phase 3)
**Date:** 2026-03-10

### Context
Session history can duoc luu tru hieu qua de tiet kiem RAM.

### Decision
3-tier memory: Hot (Redis) -> Warm (PG + Zstd) -> Cold (Disk + LZ4).

### Tier Details

| Tier | Storage | Compression | TTL | Data |
|------|---------|-------------|-----|------|
| Hot | Redis | None | 30 min | 3 recent turns |
| Warm | PostgreSQL | Zstd (column) | 7 days | Full history |
| Cold | Disk file | LZ4 | Indefinite | Archived sessions |

### Migration Rules
```
Hot -> Warm:  After 30min inactivity (Redis TTL expire, data already in PG)
Warm -> Cold: After 24h inactivity (cron job, compress + move to disk)
Cold -> Warm: On user access (decompress + load to PG, set to Hot)
```

### Trade-offs
- (+) Giam Redis memory usage (chi 3 turns, khong full history)
- (+) PG compression giam ~60% storage
- (+) Cold tier khong ton RAM
- (-) Cold -> Hot load time ~2-3s
- (-) Complexity trong session_manager.py

---

## ADR-007: Task Queue - Celery + Redis

**Status:** Accepted
**Date:** 2026-03-10

### Context
Document ingestion can async processing de khong block API response.

### Decision
Celery voi Redis lam broker (share Redis instance voi cache, different DB number).

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Celery + Redis (chosen)** | Mature, scheduling, retry | Them worker process |
| FastAPI BackgroundTasks | No extra dependency | No retry, no monitoring, lost on crash |
| Dramatiq | Simpler than Celery | Less ecosystem |
| ARQ (async Redis queue) | Lightweight, async-native | Less features |

### Config
```
Broker: redis://redis:6379/1 (DB 1, separate from cache DB 0)
Worker concurrency: 2 (RAM constraint)
Task retry: 3 times with exponential backoff
```

### Trade-offs
- (+) Document processing khong block API
- (+) Retry logic cho transient failures
- (+) Celery Beat cho periodic tasks (archival, cleanup)
- (-) Them 1 worker process (~200MB RAM)
- (-) Celery co the complex cho simple tasks

---

## ADR-008: Reranker Implementation

**Status:** Accepted (Phase 2)
**Date:** 2026-03-10

### Context
Can cross-encoder reranker de improve retrieval precision. bge-reranker-v2 khong co tren Ollama.

### Decision
Dung sentence-transformers library trong Python backend, load model BAAI/bge-reranker-v2-m3.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **sentence-transformers (chosen)** | Accurate cross-encoder, well-tested | +400MB RAM in backend |
| Ollama bge-m3 | Simple, same API | Not true cross-encoder, less accurate |
| Cohere Rerank API | Best quality | Tra phi, internet required |
| No reranker | Simple | Lower precision |

### Trade-offs
- (+) True cross-encoder scoring (query-document pair)
- (+) ~400MB RAM (fits trong 500MB backend budget khi loaded on-demand)
- (-) Load time ~3s on first use
- (-) Backend RAM tang tu ~200MB -> ~400MB khi reranker active

### Implementation Note
Load reranker lazily: chi khi co rerank request, khong load luc startup.
Unload sau 5 phut idle de free RAM.

---

## ADR-009: HyDE - Hypothetical Document Embedding

**Status:** Accepted (Phase 2)
**Date:** 2026-03-10

### Context
Users often query voi implicit terms (vd: "so sanh chi phi" thay vi "bang gia"). Vector search thuan tuy miss nhung documents nay.

### Decision
Implement HyDE: generate hypothetical answer (gemma2, 100 tokens) -> embed -> combine 70% query + 30% hyde.

### Rationale
- HyDE chuyen query tu "question space" sang "answer space"
- Embeddings cua hypothetical answer gan voi actual document hon
- Cost: 1 extra gemma2 generation (~1s) + 1 extra embedding (~0.1s)

### Trade-offs
- (+) Significant improvement cho implicit/vague queries
- (+) Khong ton them RAM (dung gemma2 da loaded)
- (-) +1s latency per query
- (-) Doi khi hypothetical answer sai huong -> worse results
- (-) Khong can thiet cho exact keyword queries

### Config
```
HyDE prompt: "Given this question, write a short paragraph answering it: {query}"
Max tokens: 100
Temperature: 0.3 (low, focused)
Combination: 0.7 * query_vec + 0.3 * hyde_vec (normalized)
```
