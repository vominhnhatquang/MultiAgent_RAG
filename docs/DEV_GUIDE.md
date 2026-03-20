# RAG Chatbot — Developer Guide

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend    │────▶│  Backend    │────▶│  Ollama     │
│  Next.js 14  │ SSE │  FastAPI    │     │  gemma2:2b  │
│  port 3000   │◀────│  port 8000  │     │  port 11434 │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┼──────┐
                    ▼      ▼      ▼
              ┌────────┐┌──────┐┌───────┐
              │Postgres││Qdrant││ Redis  │
              │pgvector││ 1.9  ││  7.2  │
              │port 5432││ 6333 ││ 6379  │
              └────────┘└──────┘└───────┘
```

**7 containers**, **9.1 GB total RAM**, hard limit **10 GB**.

---

## Quick Start

### Prerequisites

- Docker Engine 24+ with Docker Compose v2
- 10 GB free RAM
- (Optional) Gemini API key for cloud LLM fallback

### First Run

```bash
# 1. Clone and configure
cd rag-chatbot
cp .env.example .env   # Edit with your secrets

# 2. Build, start, and pull Ollama models
make init

# 3. Verify all services are healthy
make health

# 4. Open the app
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs (Swagger UI)
```

### Development Mode

```bash
make dev    # Hot-reload for backend + frontend (uses docker-compose.dev.yml overlay)
make dev-d  # Same but detached
```

### Useful Commands

```bash
make up              # Start production
make down            # Stop (keep volumes)
make down-v          # Stop + delete volumes (DESTRUCTIVE)
make logs            # Follow all logs
make logs-backend    # Follow specific service
make build           # Build images
make rebuild         # Force rebuild (no cache)
make test            # Run pytest in backend container
make ram             # RAM usage per container
make ram-watch       # Live RAM monitor (5s refresh)
make health          # Health check all services
make backup          # Backup PostgreSQL + Qdrant
make shell-backend   # Shell into backend container
make shell-postgres  # psql into PostgreSQL
make shell-redis     # redis-cli into Redis
```

---

## Project Structure

```
rag-chatbot/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── chat.py           # POST /chat (SSE), sessions, feedback
│   │   │   ├── documents.py      # Upload, list, detail, delete
│   │   │   └── health.py         # GET /health
│   │   ├── core/
│   │   │   ├── generation/
│   │   │   │   ├── streamer.py       # SSE orchestrator (main pipeline)
│   │   │   │   ├── llm_router.py     # Ollama ↔ Gemini routing
│   │   │   │   ├── guard.py          # Strict mode relevance guard
│   │   │   │   ├── mode_switch.py    # Strict ↔ General routing
│   │   │   │   ├── intent_classifier.py  # Chit-chat vs RAG
│   │   │   │   └── prompt_builder.py # System + context prompt assembly
│   │   │   ├── retrieval/
│   │   │   │   ├── pipeline.py       # Retrieval pipeline orchestrator
│   │   │   │   ├── hybrid_search.py  # BM25 + Vector + RRF fusion
│   │   │   │   ├── query_transformer.py  # HyDE + multi-query expansion
│   │   │   │   └── reranker.py       # bge-reranker-v2-m3 cross-encoder
│   │   │   ├── memory/
│   │   │   │   ├── memory_tiers.py   # Hot (Redis) + Warm (PG)
│   │   │   │   └── ollama_scheduler.py  # Model swap controller
│   │   │   └── ingestion/
│   │   │       └── pipeline.py       # Extract → chunk → embed → index
│   │   ├── db/
│   │   │   ├── postgres.py       # AsyncSession factory
│   │   │   ├── redis.py          # Redis connection
│   │   │   ├── qdrant.py         # Qdrant client
│   │   │   └── models/           # SQLAlchemy models
│   │   ├── celery_app.py         # Celery configuration
│   │   ├── tasks.py              # Celery tasks
│   │   ├── config.py             # Pydantic settings
│   │   ├── main.py               # FastAPI factory
│   │   └── exceptions.py         # Custom exceptions
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   ├── alembic/                  # Database migrations
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── app/
│   │   ├── chat/                 # Chat page
│   │   ├── upload/               # Upload page
│   │   ├── admin/                # Admin dashboard
│   │   ├── layout.tsx            # Root layout
│   │   └── page.tsx              # Landing page
│   ├── components/               # UI components
│   ├── hooks/                    # React hooks (useChat, useSession, etc.)
│   ├── lib/
│   │   └── api.ts                # API client
│   ├── types/                    # TypeScript types
│   └── Dockerfile
│
├── infra/
│   ├── docker/                   # Service-specific Dockerfiles & configs
│   │   ├── postgres/
│   │   ├── qdrant/
│   │   └── redis/
│   ├── scripts/
│   │   ├── health-check.sh       # Service health verification
│   │   ├── init-ollama.sh        # Model pulling
│   │   ├── backup-db.sh          # PostgreSQL + Qdrant backup
│   │   └── cleanup.sh            # Docker cleanup
│   └── monitoring/
│       ├── check_ram.py          # RAM monitor per container
│       └── alerts.py             # Webhook alerting (Slack/Discord)
│
├── docs/
│   ├── architecture/             # System design documents
│   ├── schemas/                  # Database & collection schemas
│   └── api/                      # API contract documentation
│
├── .agent/                       # Multi-agent coordination
│   └── handoff/
│       ├── completed/            # Reviewed handoffs
│       └── pending/              # Awaiting review
│
├── docker-compose.yml            # Production compose
├── docker-compose.dev.yml        # Dev overlay (hot reload)
├── Makefile                      # Project commands
├── STATUS.md                     # Sprint status tracker
└── improvement_plan.md           # Post-audit improvement tasks
```

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Send message, get SSE stream |
| GET | `/sessions` | List sessions (paginated) |
| GET | `/sessions/{id}` | Session detail with messages |
| DELETE | `/sessions/{id}` | Delete session |
| POST | `/sessions/{sid}/messages/{mid}/feedback` | Submit feedback |

**POST /chat** request body:
```json
{
  "session_id": "uuid or null (creates new)",
  "message": "your question here",
  "mode": "strict | general"
}
```

**SSE Events** (streamed response):
```
event: session    → { session_id, model, mode, intent }
event: sources    → { sources: [{ chunk_id, doc_name, page, score, snippet }] }
event: token      → { content: "word ", done: false }
event: done       → { done: true, sources, model, total_tokens, debug }
event: no_data    → { message, code: "GUARD_REJECTED", max_score }
event: error      → { error, code }
```

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/documents/upload` | Upload file (multipart/form-data) |
| GET | `/documents` | List documents (paginated) |
| GET | `/documents/{id}` | Document detail |
| DELETE | `/documents/{id}` | Delete document + chunks |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |

---

## Retrieval Pipeline

The query processing pipeline (in order):

```
User Query
    │
    ▼
1. Intent Classification (rule-based, bilingual)
    ├── CHIT_CHAT → Mode Switch → template or LLM
    └── RAG_QUERY ↓
    │
    ▼
2. Query Transformation (parallel)
    ├── HyDE: generate hypothetical answer → embed → blend (0.7q + 0.3h)
    └── Multi-query: expand to 3 alternative phrasings
    │
    ▼
3. Hybrid Search (parallel)
    ├── Vector search (Qdrant, cosine similarity)
    └── BM25 search (PostgreSQL tsvector)
    │
    ▼
4. RRF Fusion (k=60)
    │  score = weight / (k + rank + 1)
    ▼
5. Cross-Encoder Reranking (bge-reranker-v2-m3)
    │
    ▼
6. Strict Guard (threshold ≥ 0.7)
    │
    ▼
7. Mode Switch (strict/general routing)
    │
    ▼
8. Prompt Assembly (system + context + history)
    │
    ▼
9. LLM Generation (Ollama or Gemini, streaming)
    │
    ▼
10. SSE Streaming → Frontend
```

---

## Configuration

### Environment Variables

Key variables in `.env`:

```bash
# PostgreSQL
POSTGRES_USER=raguser
POSTGRES_PASSWORD=<your-password>
POSTGRES_DB=ragdb

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_URL=http://qdrant:6333

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=gemma2:2b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Gemini (optional, for cloud LLM fallback)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

# Force specific LLM: "gemini" | "ollama" | "" (auto)
FORCE_LLM_BACKEND=

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Dev Mode (No Docker)

Set `DEV_MODE=true` in `.env` to run backend without Docker:
- SQLite instead of PostgreSQL
- In-memory Qdrant
- fakeredis instead of Redis

```bash
cd backend
pip install -e ".[dev]"
DEV_MODE=true uvicorn app.main:app --reload --port 8000
```

---

## Memory Budget

| Container | Limit | Purpose |
|-----------|-------|---------|
| rag_ollama | 6100 MB | LLM inference (gemma2:2b = 1.6GB, nomic = 0.3GB) |
| rag_postgres | 800 MB | Database + pgvector + BM25 |
| rag_qdrant | 800 MB | Vector index |
| rag_backend | 700 MB | FastAPI + reranker model (~400MB) |
| rag_redis | 300 MB | Cache + Celery broker |
| rag_celery | 200 MB | Task worker |
| rag_frontend | 200 MB | Next.js SSR |
| **Total** | **9100 MB** | Hard limit: 10 GB |

**Peak RAM** occurs during model swap (gemma2 → llama3.1): ~9.5 GB for ~5 seconds.

Monitor with:
```bash
make ram          # Snapshot
make ram-watch    # Live (5s refresh)
```

Alerts fire at:
- WARNING: total > 9000 MB
- CRITICAL: total > 9500 MB (webhook alert if `ALERT_WEBHOOK_URL` is set)

---

## Ollama Model Management

Models used:

| Model | Size | Purpose | Loaded |
|-------|------|---------|--------|
| nomic-embed-text | 0.3 GB | Document + query embeddings (768-dim) | Always |
| gemma2:2b | 1.6 GB | Default chat model | Always |
| bge-reranker-v2-m3 | 0.4 GB | Cross-encoder reranking (CPU, sentence-transformers) | Lazy |
| llama3.1:8b | 4.7 GB | On-demand for hard queries | On-demand swap |

**Swap strategy** (`OLLAMA_MAX_LOADED_MODELS=1`):
1. Unload gemma2 (`keep_alive=0`)
2. Wait 2 seconds for memory release
3. Load llama3.1
4. After response, unload llama3.1 and reload gemma2

See `backend/app/core/memory/ollama_scheduler.py` for implementation.

---

## Database Schema

### PostgreSQL Tables

- **documents**: id, filename, file_type, file_size_bytes, sha256_hash, status, chunk_count, error_message, timestamps
- **chunks**: id, document_id, content, page_number, chunk_index, embedding (vector 768), metadata (JSONB), tsvector (BM25)
- **sessions**: id, title, mode, tier, message_count, timestamps
- **messages**: id, session_id, role, content, sources (JSONB), model_used, timestamps
- **feedbacks**: id, message_id, session_id, rating, comment, timestamps

### Qdrant Collection

- Collection: `document_chunks`
- Vector size: 768 (nomic-embed-text)
- Distance: Cosine
- Payload: `doc_id`, `doc_name`, `page`, `chunk_index`, `content_preview`

---

## Testing

```bash
# Run all tests inside container
make test

# Run specific test file
docker compose exec backend pytest tests/unit/test_guard.py -v

# Run with coverage
docker compose exec backend pytest tests/ --cov=app --cov-report=term-missing

# Dev mode (local, no Docker)
cd backend
DEV_MODE=true pytest tests/unit/ -v
```

Test structure:
- `tests/unit/` — Pure logic tests (guard, intent classifier, RRF, etc.)
- `tests/integration/` — Tests with DB/service dependencies
- `tests/fixtures/` — Shared test data

---

## Architecture Decisions (ADRs)

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Qdrant primary + pgvector backup | Qdrant faster for ANN, pgvector for BM25 hybrid |
| ADR-002 | Ollama swap (MAX_LOADED=1) | 10GB RAM limit prevents concurrent models |
| ADR-003 | Gemini API fallback | Free tier for hard queries when local model insufficient |
| ADR-004 | BM25 + Vector + RRF (k=60) | Better recall than vector-only for keyword-heavy queries |
| ADR-005 | SSE streaming | Real-time UX, simpler than WebSocket for chat |
| ADR-006 | 3-tier memory (Hot/Warm/Cold) | Balance speed vs storage for session history |
| ADR-007 | Celery + Redis | Async document processing, prevents API blocking |
| ADR-008 | bge-reranker-v2 (sentence-transformers) | Best quality/size tradeoff, CPU-only, lazy loaded |
| ADR-009 | HyDE 0.7/0.3 | Empirical weighting: query signal dominant, HyDE supplementary |

Full details: `docs/architecture/tech-decisions.md`

---

## Multi-Agent Workflow

This project uses a 4-agent development team:

| Agent | Role | Scope |
|-------|------|-------|
| **Alpha** | System Architect | Architecture, API contracts, reviews |
| **Beta** | Backend Developer | FastAPI, retrieval, generation, tests |
| **Delta** | Frontend Developer | Next.js, components, hooks, UI |
| **Epsilon** | DevOps Engineer | Docker, infra, monitoring, scripts |

### Handoff Protocol

1. Agent creates handoff JSON in `.agent/handoff/pending/`
2. Alpha reviews against acceptance criteria
3. Move to `.agent/handoff/completed/` if accepted
4. Update `STATUS.md`

File naming: `{agent}-phase{N}-{task}-{date}.json`

---

## Known Gaps & Improvement Plan

See `improvement_plan.md` for the full post-audit improvement plan:

| Priority | Task | Impact |
|----------|------|--------|
| HIGH | Cold tier storage (Zstd compression) | ADR-006 compliance |
| HIGH | Celery document ingestion | ADR-007 compliance, async upload |
| MEDIUM | Fix feedback API wildcard path | Frontend bug |
| MEDIUM | Celery Beat scheduled tasks | Automated maintenance |
| MEDIUM | Admin API endpoints | Dashboard real data |
| MEDIUM | Rate limiting middleware | API protection |
| LOW | Integration tests | Coverage 60% → 80% |
| LOW | Error boundaries + loading states | UI resilience |
| LOW | Session PATCH endpoint | Edit session title/mode |

---

## Troubleshooting (Dev)

| Issue | Fix |
|-------|-----|
| Docker daemon not running | `make docker-start` (WSL2) |
| Ollama model not found | `make init-ollama` |
| Backend can't connect to DB | Check `POSTGRES_PASSWORD` in `.env`, run `make health` |
| Redis connection refused | Verify redis container: `make logs-redis` |
| Qdrant unhealthy | Check port 6333: `curl http://localhost:6333/healthz` |
| Reranker model download slow | First query triggers download (~400MB); wait or pre-download |
| OOM kill | Check `make ram`; reduce `OLLAMA_KEEP_ALIVE` or disable llama3.1 swap |
| Alembic migration error | `make migrate` or `docker compose exec backend alembic upgrade head` |
| Frontend build fails | `cd frontend && npm install && npm run build` |
