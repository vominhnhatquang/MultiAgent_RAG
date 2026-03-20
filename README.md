# RAG Chatbot — Document Q&A with AI

Hệ thống chatbot trả lời câu hỏi chuyên môn dựa trên tài liệu đã upload, sử dụng Retrieval-Augmented Generation (RAG) với hybrid search, guard check, và LLM streaming.

**Version:** 1.1.0 | **RAM Budget:** 10 GB | **Containers:** 8

---

## Quick Start

```bash
# 1. Clone & cấu hình
cp .env.example .env          # điền GEMINI_API_KEY

# 2. Khởi động
docker compose up -d           # ~2 phút để init

# 3. Kiểm tra
curl http://localhost:8000/api/v1/health

# 4. Truy cập
# Frontend:  http://localhost:3000
# API Docs:  http://localhost:8000/docs
# Qdrant UI: http://localhost:6333/dashboard
```

> Hướng dẫn chi tiết: [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI · Python 3.11 · Pydantic v2 |
| Frontend | Next.js 14 (App Router) · TypeScript · Tailwind CSS |
| Vector DB | Qdrant v1.17.0 (scalar quantization INT8) |
| Database | PostgreSQL 16 (BM25 full-text search) |
| Cache | Redis 7 (session hot tier) |
| Embedding | nomic-embed-text (768 dims) via Ollama |
| LLM | Gemini 2.5 Flash (cloud) / Gemma 2 2B + Llama 3.1 8B (local) |
| Task Queue | Celery + Redis (async document processing) |

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│  LLM Engine  │
│  Next.js 14  │ SSE │  FastAPI     │     │ Gemini/Ollama│
│  :3000       │◀────│  :8000       │     │              │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                    ┌───────┼───────┐
                    │       │       │
               ┌────▼──┐ ┌─▼────┐ ┌▼──────┐
               │Postgres│ │Qdrant│ │ Redis  │
               │  :5432 │ │:6333 │ │ :6379  │
               └────────┘ └──────┘ └────────┘
                    │
               ┌────▼─────┐
               │  Celery   │
               │  Worker   │
               └───────────┘
```

### RAG Pipeline

```
Query → Intent Classify → Difficulty Classify → HyDE Transform
  → Hybrid Search (Vector + BM25) → RRF Fusion
  → Guard Check (threshold 0.4) → LLM Generate → SSE Stream
```

---

## Features

### Core
- 📄 **Document Upload** — PDF, DOCX, MD, TXT (max 50MB) → async processing via Celery
- 🔍 **Hybrid Search** — Vector search (Qdrant) + BM25 (PostgreSQL) + Reciprocal Rank Fusion
- 🤖 **HyDE** — Hypothetical Document Embedding for better retrieval
- 🛡️ **Strict Guard** — Rejects low-relevance answers (cosine similarity < 0.4)
- 💬 **SSE Streaming** — Real-time token streaming with source citations
- 🔀 **Mode Switch** — Strict (only documents) / General (allows general knowledge)

### LLM Routing & Display ⭐
- **Query difficulty classification** — easy / medium / hard (rule-based)
- **Difficulty-based model routing** — easy→chat model, hard→heavy model
- **UI badges** — Mỗi response hiển thị: model name + difficulty badge (màu sắc)

### Memory Tiers
- **Hot** — Redis (30 min TTL, last 6 messages)
- **Warm** — PostgreSQL (7 days, Zstd compressed)
- **Cold** — Disk archive (LZ4)

---

## RAM Budget (10 GB)

| Service | Limit | Purpose |
|---------|-------|---------|
| Ollama | 6,500 MB | LLM inference (models loaded on demand) |
| PostgreSQL | 800 MB | Relational data + BM25 search |
| Qdrant | 800 MB | Vector search (scalar quantization) |
| Backend | 700 MB | FastAPI + retrieval pipeline |
| Celery | 500 MB | Async document processing |
| Redis | 300 MB | Session cache + task queue |
| Frontend | 200 MB | Next.js SSR |
| Celery Beat | 100 MB | Scheduled tasks |
| **Total** | **~9.9 GB** | |

---

## API

Base URL: `http://localhost:8000/api/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/documents/upload` | Upload document (multipart) |
| `GET` | `/documents` | List documents + pagination |
| `GET` | `/documents/{id}` | Document status + chunk count |
| `POST` | `/chat` | Chat with SSE streaming |
| `GET` | `/sessions` | List chat sessions |
| `GET` | `/sessions/{id}` | Session + message history |
| `POST` | `/feedback` | Submit thumbs up/down |
| `GET` | `/health` | Health check |
| `GET` | `/admin/stats` | System statistics |

Interactive docs: `http://localhost:8000/docs`

---

## Data Storage

> **Tại sao các folder `data/postgres`, `data/qdrant`, `data/redis`, `data/ollama` trống?**
>
> Dữ liệu KHÔNG lưu trên host filesystem. Docker Compose sử dụng **named volumes**
> (`postgres_data`, `qdrant_data`, `redis_data`, `ollama_data`) được quản lý bởi
> Docker Engine. Các folder trong `data/` chỉ là placeholder cho backup scripts.

| Data | Storage | Location |
|------|---------|----------|
| Document metadata, chunks text, sessions | PostgreSQL | Docker volume `postgres_data` |
| Vector embeddings (768-dim) | Qdrant | Docker volume `qdrant_data` |
| Session hot cache | Redis | Docker volume `redis_data` |
| LLM model weights | Ollama | Docker volume `ollama_data` |
| Uploaded raw files | Shared volume | Docker volume `upload_data` |
| Pre-processed chunks (legacy) | Host filesystem | `data/processed/` |

Xem volumes: `docker volume ls | grep rag`

---

## Project Structure

```
rag-chatbot/
├── backend/                # FastAPI application
│   └── app/
│       ├── api/v1/         # REST endpoints
│       ├── core/
│       │   ├── ingestion/  # Extract → Chunk → Embed → Index
│       │   ├── retrieval/  # HyDE + Vector + BM25 + Rerank
│       │   ├── generation/ # Intent → Difficulty → Guard → LLM → Stream
│       │   └── memory/     # Hot/Warm/Cold tiers
│       ├── db/             # PostgreSQL, Redis, Qdrant clients
│       └── tasks.py        # Celery task definitions
├── frontend/               # Next.js 14 application
│   ├── app/                # Pages: chat, upload, admin
│   ├── components/chat/    # MessageBubble, StreamingText, SourceCitation
│   ├── hooks/              # useChat, useSession, useUpload
│   └── lib/                # API client, SSE parser
├── data/                   # Host-side data (uploads + backups)
│   ├── uploads/raw/        # Original uploaded files
│   └── processed/          # Legacy processed chunks
├── docs/
│   ├── DEV_GUIDE.md        # Complete startup runbook
│   ├── DELIVERY_REPORT.md  # Client delivery report
│   └── architecture/       # System overview, data flow, memory budget, ADRs
├── docker-compose.yml      # 8-service stack
├── .env                    # Configuration
└── Makefile                # Shortcuts
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md) | Complete startup guide + troubleshooting |
| [docs/DELIVERY_REPORT.md](docs/DELIVERY_REPORT.md) | Client delivery report (bilingual) |
| [docs/architecture/system-overview.md](docs/architecture/system-overview.md) | Architecture diagrams, service topology |
| [docs/architecture/data-flow.md](docs/architecture/data-flow.md) | Document pipeline + Chat pipeline |
| [docs/architecture/memory-budget-10gb.md](docs/architecture/memory-budget-10gb.md) | RAM allocation per service |
| [docs/architecture/tech-decisions.md](docs/architecture/tech-decisions.md) | 13 Architecture Decision Records |

---

## Environment Variables

Key variables in `.env`:

```bash
# LLM Backend (gemini | ollama)
FORCE_LLM_BACKEND=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash

# Ollama Models (full HuggingFace paths required)
OLLAMA_CHAT_MODEL=hf.co/MaziyarPanahi/gemma-2-2b-it-GGUF:Q8_0
OLLAMA_HEAVY_MODEL=hf.co/modularai/Llama-3.1-8B-Instruct-GGUF:Q4_K_M
OLLAMA_EMBED_MODEL=nomic-embed-text

# PostgreSQL
POSTGRES_USER=raguser
POSTGRES_PASSWORD=ragpass
POSTGRES_DB=ragdb
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Containers not starting | `docker compose down -v && docker compose up -d` |
| Ollama OOM killed | Reduce `num_ctx` or switch to smaller model |
| "Retrieval failed" | Check backend logs: `docker logs rag_backend --tail 50` |
| CORS errors | Usually masks a 500 error — check backend logs first |
| Upload not processed | Verify shared volume: `docker exec rag_celery ls /app/data/uploads/raw/` |

Full troubleshooting: [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)

---

*Built with ❤️ — RAG Chatbot v1.1.0*
