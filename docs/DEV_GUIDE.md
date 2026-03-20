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
              │pgvector││ 1.17 ││  7.2  │
              │port 5432││ 6333 ││ 6379  │
              └────────┘└──────┘└───────┘
```

**8 containers** (backend, celery, celery-beat, frontend, postgres, qdrant, redis, ollama), **9.1 GB total RAM**, hard limit **10 GB**.

---

## Quick Start

### Prerequisites

- Docker Engine 24+ with Docker Compose v2
- Node.js 20+ if you want to run the frontend outside Docker
- Python 3.12+ if you want to run the backend outside Docker
- 10 GB free RAM
- (Optional) Gemini API key for cloud LLM fallback

### First Run

```bash
# 1. Clone and configure
cd rag-chatbot
cp .env.example .env   # Edit with your secrets

# 2. Make sure Docker daemon is running
make check-docker || make docker-start

# 3. Build images, start all containers, pull Ollama models, wait for health
make init

# 4. Verify all services are healthy
make ps
make health

# 5. Open the app
# Frontend: http://localhost:3000
# Backend Swagger: http://localhost:8000/docs
# Backend health:  http://localhost:8000/health
```

### Development Mode

#### Option A — Everything in Docker with hot reload

```bash
make dev    # Hot-reload for backend + frontend (uses docker-compose.dev.yml overlay)
make dev-d  # Same but detached
```

This mode starts all 8 services:

- Infra daemons: PostgreSQL, Redis, Qdrant, Ollama
- App processes: FastAPI backend, Celery worker, Celery beat (scheduler), Next.js frontend

Use this when you want the simplest dev setup.

#### Option B — Split startup: daemon + infra + backend + frontend

Use this when you want to start each layer separately and see exactly what is running.

**Terminal 1 — Docker daemon**

```bash
cd rag-chatbot
make check-docker || make docker-start
```

**Terminal 2 — Start infra daemons only**

```bash
cd rag-chatbot
docker compose up -d postgres redis qdrant ollama
make init-ollama
```

At this point the infrastructure daemons available are:

- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- Qdrant on `localhost:6333`
- Ollama on `localhost:11434`

**Terminal 3 — Start backend + worker in dev mode (Docker)**

```bash
cd rag-chatbot
docker compose -f docker-compose.yml -f docker-compose.dev.yml up backend celery celery-beat
```

Backend will be available at:

- `http://localhost:8000/docs`
- `http://localhost:8000/health`

**Terminal 4 — Start frontend locally**

```bash
cd rag-chatbot/frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

Frontend will be available at `http://localhost:3000`.

**Verification**

```bash
curl http://localhost:11434/api/tags
curl http://localhost:6333/healthz
curl http://localhost:8000/health
curl http://localhost:3000
```

### Useful Commands

```bash
make check-docker    # Verify Docker daemon
make docker-start    # Start Docker daemon (mainly for WSL2/Linux without Docker Desktop)
make up              # Start production
make ps              # Show running containers
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
# PostgreSQL (primary keys — POSTGRES_USER/PASSWORD are auto-derived aliases)
PG_USER=raguser
PG_PASSWORD=<your-password>
PG_DB=ragdb

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_URL=http://qdrant:6333

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=gemma2:2b               # compose default (or HuggingFace GGUF — see .env.example)
OLLAMA_EMBED_MODEL=nomic-embed-text

# Gemini (optional, for cloud LLM fallback)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

# Force specific LLM: "gemini" | "ollama" | "" (auto)
FORCE_LLM_BACKEND=

# Frontend (include /api/v1 — the backend mounts routes at this prefix)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Dev Mode (No Docker)

If you want to run the **backend process** directly on the host, use `DEV_MODE=true`.
In this mode the backend uses:

- SQLite instead of PostgreSQL
- In-memory Qdrant
- fakeredis instead of Redis
- External Ollama at `http://localhost:11434` unless you force Gemini

This is useful when you want to run the app processes manually while keeping only Ollama as a daemon.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" aiosqlite fakeredis
DEV_MODE=true uvicorn app.main:app --reload --port 8000
```

If you also want the frontend outside Docker:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

Recommended combinations:

- **Fastest path to a working app:** `make check-docker || make docker-start` → `make init`
- **Best development experience:** `make dev`
- **Most explicit process split:** infra daemons via Docker, backend/frontend in separate terminals

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
| Backend can't connect to DB | Check `PG_PASSWORD` in `.env`; verify compose passes `POSTGRES_HOST=postgres` env var; run `make health` |
| Redis connection refused | Verify redis container: `make logs-redis` |
| Qdrant unhealthy | Check port 6333: `curl http://localhost:6333/healthz` |
| Reranker model download slow | First query triggers download (~400MB); wait or pre-download |
| OOM kill | Check `make ram`; reduce `OLLAMA_KEEP_ALIVE` or disable llama3.1 swap |
| Alembic migration error | `make migrate` or `docker compose exec backend alembic upgrade head` |
| Frontend build fails | `cd frontend && npm install && npm run build` |
| systemd boot hangs (WSL2) | Check `/etc/fstab` for invalid UUID lines; comment out and `sudo systemctl daemon-reload` |
| Docker build cache corrupt | `docker builder prune -af && docker system prune -af` then rebuild |
| Ghost containers (can't rm) | Stop Docker, `sudo rm -rf /var/lib/docker/containers`, restart Docker |
| Port 11434 in use | Host Ollama running: `sudo kill <PID>` then `docker compose up -d ollama` |
| `ModuleNotFoundError` in backend | Dockerfile may hardcode deps; ensure it uses `uv pip install .` from `pyproject.toml` |
| Build context too large (>100MB) | Add `.dockerignore` to `backend/` and `frontend/` excluding `.venv`, `node_modules` |
| Admin dashboard error (`used_gb undefined`) | Backend `/admin/memory` response format mismatch — must return `{total_gb, used_gb, services: {name: {used_mb, limit_mb}}}` |
| CORS error masking 500 | Fix the underlying 500 first (e.g., run `alembic upgrade head`); CORS headers only appear on successful responses |
| `QuantizationConfig` TypeError | qdrant-client 1.17+ — pass `ScalarQuantization(...)` directly, don't wrap in `QuantizationConfig()` |
| Qdrant `search()` method missing | qdrant-client 1.17+ — use `query_points()` instead, access results via `.points` |
| Retrieval always fails with "low_relevance" | Without cross-encoder reranker, pipeline uses vector cosine similarity for guard (not RRF) — threshold 0.4 |
| Celery worker OOM killed | Increase `mem_limit` to 500m in docker-compose.yml, set `--concurrency=1` |
| Celery "Event loop is closed" | Indexer must create a fresh `AsyncQdrantClient` per task (not share global singleton across event loops) |
| Upload file not found by Celery | Backend and Celery need a shared Docker volume for `data/uploads/` |
| Document status stuck in "queued" | Check constraint `chk_documents_status` must include 'queued' status |
| Ollama model not found (404) | HuggingFace models need full path: `hf.co/MaziyarPanahi/gemma-2-2b-it-GGUF:Q8_0` not just `gemma-2-2b-it-GGUF:Q8_0` |
| BM25 `AmbiguousParameterError` | Use `CAST(:doc_filter AS uuid)` in SQL to help asyncpg infer NULL parameter types |

---

## Command Validation Summary

All documented `make` targets, compose configs, scripts, and file references in this guide
have been validated against the actual codebase. Last verified: 2026-03-20 (all 8 services healthy, 14/14 checks pass).

| Category | Tests | Pass | Fail |
|----------|-------|------|------|
| File/script existence | 12 | 12 | 0 |
| Make targets | 31 | 31 | 0 |
| Compose config validation | 2 | 2 | 0 |
| Runtime commands | 5 | 5 | 0 |
| Content accuracy | 6 | 6 | 0 (fixed) |
| Full startup (make init) | 1 | 1 | 0 |
| Health checks (make health) | 14 | 14 | 0 |

Fixes applied during validation:
- Service count corrected: 7 → 8 (celery-beat was missing)
- Env var names: `POSTGRES_USER`→`PG_USER`, `POSTGRES_PASSWORD`→`PG_PASSWORD` (match `.env.example` primary keys)
- Option B Terminal 3: added `celery-beat` to compose up command
- Option A description: added Celery beat to service list
- Troubleshooting: `POSTGRES_PASSWORD` reference → `PG_PASSWORD`
- Backend Dockerfile: switched from hardcoded pip list to `uv pip install .` (was missing 7 packages including structlog)
- docker-compose.yml: added `POSTGRES_HOST`, `REDIS_HOST`, `QDRANT_HOST` env vars (config.py needs individual fields, not just URL)
- Added `.dockerignore` for backend/ and frontend/ (build context reduced from ~1GB to ~2MB)
