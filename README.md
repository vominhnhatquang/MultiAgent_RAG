# RAG Chatbot — 10GB RAM Optimized

Strict RAG chatbot chạy hoàn toàn local với hybrid LLM routing, trong giới hạn **10GB RAM**.

---

## Quick Start

```bash
# 1. Clone & cấu hình
cp .env.example .env
# Mở .env → điền GEMINI_API_KEY

# 2. Khởi động tất cả services
make up

# 3. Pull models (lần đầu, ~7GB download)
make pull-models

# 4. Kiểm tra health
make health

# 5. Truy cập
open http://localhost:3000
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI · Python 3.12 · Pydantic v2 |
| Frontend | Next.js 14 (App Router) · TypeScript · Tailwind CSS |
| Vector DB | Qdrant (primary) · pgvector (backup) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| LLM local | Ollama · gemma2:2b · nomic-embed-text · bge-reranker-v2 |
| LLM cloud | Gemini API (hard queries) |
| Task queue | Celery + Redis |

---

## RAM Budget (10GB Hard Limit)

| Service | Limit | Notes |
|---------|-------|-------|
| Ollama | 6.5 GB | nomic (0.3) + gemma2 (1.6) + reranker (0.4) |
| PostgreSQL | 0.8 GB | shared_buffers=256MB |
| Qdrant | 0.8 GB | on_disk_payload=true |
| Redis | 0.3 GB | allkeys-lru eviction |
| Backend | 0.5 GB | 2 Uvicorn workers |
| Frontend | 0.3 GB | Next.js SSR |
| OS + Buffer | 0.8 GB | headroom |

> **Quy tắc vàng:** Không bao giờ load đồng thời `gemma2:2b` (1.6GB) và `llama3.1:8b` (4.7GB). Khi cần llama3.1: unload gemma2 → load llama3.1 → generate → unload → reload gemma2.

---

## Features theo Phase

### Phase 1 — MVP ✅
- Upload PDF/DOCX/MD → extract → chunk → embed → index
- Basic vector search (Qdrant)
- Chat với SSE streaming (gemma2:2b)
- Session management
- Sidebar + Chat UI + Upload UI

### Phase 2 — Intelligence 🔄
- **HyDE**: Generate hypothetical answer → combine embeddings (0.7 query + 0.3 hyde)
- **Hybrid Search**: BM25 (PostgreSQL) + Vector (Qdrant) + RRF fusion
- **Reranker**: bge-reranker-v2 cross-encoder → top 20 → top 5
- **Strict Guard**: relevance < 0.7 → trả về "Không có thông tin"
- **Mode Switch**: Strict (chỉ RAG) ↔ General (cho phép chit-chat)
- **LLM Router**: Easy→gemma2 / Hard→Gemini API / Offline→llama3.1

### Phase 3 — Production
- **Memory Tiers**: Hot (Redis 30min) → Warm (PG+Zstd 7 ngày) → Cold (Disk+LZ4)
- **Ollama Scheduler**: Auto swap model theo demand + RAM budget
- **Monitoring**: RAM per service, health endpoint, alerts
- **Backup**: `make backup` → tar.gz (PG dump + Qdrant snapshot)

---

## API

Base URL: `http://localhost:8000/api/v1`

```
POST /documents/upload    Upload PDF/DOCX/MD (max 50MB)
GET  /documents           List documents
GET  /documents/{id}      Document status + chunk count

POST /chat               Chat với SSE streaming
GET  /sessions           List sessions
GET  /sessions/{id}      Session + message history

GET  /health             Health check
GET  /health/detailed    Services status + RAM usage
GET  /admin/stats        System statistics
```

Xem [docs/api/endpoints.md](docs/api/endpoints.md) để biết đầy đủ request/response format.

---

## Project Structure

```
rag-chatbot/
├── backend/           # FastAPI app (Owner: Beta)
│   └── app/
│       ├── api/       # Routes + Pydantic schemas
│       ├── core/      # Business logic
│       │   ├── ingestion/   # Document pipeline
│       │   ├── retrieval/   # HyDE + Hybrid search + Rerank
│       │   ├── generation/  # Guard + Router + Stream
│       │   └── memory/      # Session tiers + Ollama scheduler
│       ├── db/        # PostgreSQL + Redis + Qdrant clients
│       └── integrations/    # Ollama + Gemini clients
├── frontend/          # Next.js 14 (Owner: Delta)
│   └── app/           # Pages: chat, upload, admin
├── infra/             # Docker + scripts (Owner: Epsilon)
├── docs/              # Architecture docs (Owner: Alpha)
│   ├── architecture/  # system-overview, data-flow, memory-budget, ADRs
│   ├── api/           # endpoints.md
│   └── schemas/       # database-schema.sql, qdrant-collection.json, erd
├── agents/            # Agent prompts + shared contracts
│   └── shared/
│       ├── contracts/API_CONTRACT.md
│       └── schemas/DATABASE_SCHEMA.md
└── STATUS.md          # Sprint tracking (single source of truth)
```

---

## Makefile Commands

```bash
make up           # docker-compose up -d (tất cả services)
make down         # docker-compose down
make logs         # Xem logs tất cả services
make health       # Chạy health-check script
make pull-models  # Pull Ollama models (nomic + gemma2 + llama3.1)
make migrate      # Chạy Alembic migrations
make test         # Chạy pytest
make backup       # Backup PostgreSQL + Qdrant snapshot
make stats        # docker stats (RAM per container)
```

---

## Environment Variables

```bash
# PostgreSQL
PG_USER=raguser
PG_PASSWORD=changeme
PG_DB=ragdb

# Ollama
OLLAMA_URL=http://ollama:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=gemma2:2b

# Gemini (REQUIRED cho hard queries)
GEMINI_API_KEY=your_key_here

# App
STRICT_GUARD_THRESHOLD=0.7   # Relevance threshold cho Strict mode
CORS_ORIGINS=http://localhost:3000
```

Xem [.env.example](.env.example) để biết đầy đủ.

---

## Troubleshooting

**Ollama OOM killed:**
```bash
docker logs ollama | grep -i "killed\|oom"
# Fix: giảm context length trong API call
# "options": {"num_ctx": 2048}
```

**Qdrant collection not found:**
```bash
make migrate   # hoặc
curl -X PUT http://localhost:6333/collections/document_chunks \
  -d '{"vectors":{"size":768,"distance":"Cosine"}}'
```

**RAM vượt 9GB:**
```bash
make stats     # xem container nào tốn RAM
# Unload idle models:
curl -X DELETE http://localhost:11434/api/delete -d '{"name":"llama3.1:8b"}'
```

---

## Documentation

| File | Nội dung |
|------|---------|
| [docs/architecture/system-overview.md](docs/architecture/system-overview.md) | Architecture diagrams, service topology |
| [docs/architecture/data-flow.md](docs/architecture/data-flow.md) | Document pipeline + Chat pipeline chi tiết |
| [docs/architecture/memory-budget-10gb.md](docs/architecture/memory-budget-10gb.md) | RAM allocation, swap strategy |
| [docs/architecture/tech-decisions.md](docs/architecture/tech-decisions.md) | 9 ADRs |
| [docs/api/endpoints.md](docs/api/endpoints.md) | API reference đầy đủ |
| [docs/schemas/database-schema.sql](docs/schemas/database-schema.sql) | DDL PostgreSQL |
| [STATUS.md](STATUS.md) | Sprint tracking |
