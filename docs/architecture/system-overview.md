# System Overview - RAG Chatbot 10GB
## High-Level Architecture Document

**Author:** Alpha (System Architect)
**Version:** 1.1
**Updated:** 2026-03-20 — Reconciled with deployed system (model paths, memory limits, guard threshold)
**Constraint:** 10GB RAM hard limit

---

## 1. System Context

RAG Chatbot la mot he thong hoi dap thong minh dua tren tai lieu, hoat dong trong gioi han 10GB RAM. He thong ho tro 2 che do: **Strict** (chi tra loi dua tren tai lieu) va **General** (cho phep hoi dap huong dan).

### Actors
- **End User**: Upload tai lieu, dat cau hoi, nhan phan hoi
- **Admin**: Quan ly tai lieu, theo doi RAM, reindex

---

## 2. High-Level Architecture

```mermaid
graph TB
    subgraph CLIENT["Client Layer"]
        UI[Next.js 14 Frontend<br/>Port 3000<br/>0.3GB RAM]
    end

    subgraph GATEWAY["API Gateway"]
        API[FastAPI Backend<br/>Port 8000<br/>0.5GB RAM]
    end

    subgraph PROCESSING["Processing Layer"]
        direction LR
        DP[Document Pipeline<br/>Extract > Clean > Chunk<br/>> Enrich > Embed > Index]
        CP[Chat Pipeline<br/>Intent > HyDE > Retrieve<br/>> Rerank > Guard > Generate]
        CW[Celery Workers<br/>Async Document Processing]
    end

    subgraph AI["AI Layer (6.5GB RAM)"]
        direction LR
        OL[Ollama Server<br/>Port 11434]
        GM[Gemini API<br/>Cloud - 0GB local]
    end

    subgraph MODELS["Local Models"]
        NE[nomic-embed-text<br/>0.3GB - Always]
        G2[gemma-2-2b-it Q8_0 GGUF<br/>1.6GB - Default]
        RR[bge-reranker-v2<br/>0.4GB - Phase 2]
        L3[llama3.1:8b<br/>4.7GB - On-demand SWAP]
    end

    subgraph STORAGE["Storage Layer"]
        PG[(PostgreSQL 16<br/>+ pgvector<br/>Port 5432<br/>0.8GB)]
        QD[(Qdrant<br/>Vector DB<br/>Port 6333<br/>0.8GB)]
        RD[(Redis 7<br/>Hot Cache<br/>Port 6379<br/>0.3GB)]
    end

    UI -->|REST + SSE| API
    API --> DP
    API --> CP
    API -->|Enqueue| CW
    CW --> DP

    DP -->|Embed| OL
    CP -->|Generate| OL
    CP -->|Hard queries| GM

    OL --> NE
    OL --> G2
    OL --> RR
    OL -.->|Swap| L3

    DP -->|Metadata| PG
    DP -->|Vectors| QD
    CP -->|BM25 Search| PG
    CP -->|Semantic Search| QD
    CP -->|Session Cache| RD

    style L3 stroke-dasharray: 5 5
    style GM fill:#e1f5fe
```

---

## 3. Service Topology

```mermaid
graph LR
    subgraph DOCKER["Docker Compose Network: rag-net"]
        FE[frontend:3000]
        BE[backend:8000]
        PG[postgres:5432]
        QD[qdrant:6333]
        RD[redis:6379]
        OL[ollama:11434]
        CK[celery-worker]
        CB[celery-beat]
    end

    FE -->|HTTP| BE
    BE -->|asyncpg| PG
    BE -->|HTTP| QD
    BE -->|aioredis| RD
    BE -->|HTTP| OL
    CK -->|asyncpg| PG
    CK -->|HTTP| QD
    CK -->|HTTP| OL
    CB -->|schedule| CK
    CK -->|broker| RD
    BE -.->|upload_data volume| CK
```

### Port Mapping

| Service      | Internal Port | External Port | Protocol |
|-------------|---------------|---------------|----------|
| Frontend    | 3000          | 3000          | HTTP     |
| Backend     | 8000          | 8000          | HTTP     |
| PostgreSQL  | 5432          | 5432          | TCP      |
| Qdrant      | 6333          | 6333          | HTTP     |
| Qdrant gRPC | 6334          | 6334          | gRPC     |
| Redis       | 6379          | 6379          | TCP      |
| Ollama      | 11434         | 11434         | HTTP     |

---

## 4. Layer Responsibilities

### 4.1 Client Layer (Next.js 14)
- Server-Side Rendering cho SEO va initial load
- SSE (Server-Sent Events) client cho streaming responses
- Mode Toggle UI (Strict / General)
- Document upload voi drag-and-drop
- Session management (sidebar)

### 4.2 API Gateway (FastAPI)
- REST API voi OpenAPI 3.1 auto-docs
- SSE streaming endpoint cho chat
- Request validation (Pydantic v2)
- CORS middleware
- Dependency injection (DB sessions, Redis, Qdrant clients)

### 4.3 Processing Layer
- **Document Pipeline**: Extract > Clean > Chunk > Enrich > Embed > Index
- **Chat Pipeline**: Intent Classify > HyDE > Hybrid Retrieve > Rerank > Guard > Generate > Stream
- **Workers**: Celery cho async document processing, session archival

### 4.4 AI Layer
- **Ollama**: Local model serving voi memory-aware scheduling
- **Gemini API**: Cloud fallback cho hard queries (khong ton RAM local)
- **Model Swap**: Chi 1 large LLM (gemma-2-2b-it HOAC llama3.1) tai 1 thoi diem

### 4.5 Storage Layer
- **PostgreSQL 16 + pgvector**: Metadata, chat history, BM25 full-text search, backup vector storage
- **Qdrant**: Primary vector search (HNSW index, 768-dim cosine)
- **Redis 7**: Hot session cache (3 recent turns, TTL 30min), Celery broker

---

## 5. Phase Deployment View

```mermaid
gantt
    title RAG Chatbot - 3 Phase Delivery
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m

    section Phase 1 - MVP
    Infra Setup (Epsilon)        :p1a, 2026-03-10, 2d
    Schema + Contract (Alpha)    :p1b, 2026-03-10, 1d
    Backend Basic (Beta)         :p1c, after p1b, 2d
    Frontend Basic (Delta)       :p1d, after p1c, 1d

    section Phase 2 - Intelligence
    Contract Update (Alpha)      :p2a, after p1d, 1d
    HyDE + Rerank + Guard (Beta) :p2b, after p2a, 3d
    Mode Switch UI (Delta)       :p2d, after p2a, 2d
    Full Docker (Epsilon)        :p2e, after p1d, 2d

    section Phase 3 - Production
    ADR + Final Contract (Alpha) :p3a, after p2b, 1d
    Memory Tiers (Beta)          :p3b, after p3a, 2d
    UI Polish (Delta)            :p3d, after p2d, 2d
    Monitoring + Backup (Epsilon):p3e, after p2e, 2d
```

---

## 6. Key Design Decisions (Summary)

| Decision | Choice | Reason |
|----------|--------|--------|
| Vector DB | Qdrant (separate) | Chuyen biet cho vector search, HNSW tuning, khong share resources voi PG |
| Backup vectors | pgvector (PostgreSQL) | Fallback khi Qdrant down, dung cho BM25 hybrid |
| LLM serving | Ollama | Self-hosted, model swap API, memory control |
| Cloud fallback | Gemini API | Free tier 15 RPM, khong ton RAM local |
| Task queue | Celery + Redis | Mature, async document processing, cron scheduling |
| Frontend | Next.js 14 App Router | SSR, streaming support, TypeScript |
| Streaming | SSE (not WebSocket) | Simpler, unidirectional (server > client), HTTP/2 compatible |

---

## 7. Constraints & Boundaries

1. **RAM Hard Limit**: Tong 10GB - moi component co memory limit trong docker-compose
2. **Model Exclusivity**: KHONG BAO GIO load dong thoi gemma-2-2b-it (1.6GB) va llama3.1 (4.7GB)
3. **Concurrency**: Max 5-10 concurrent chat sessions
4. **File Size**: Max upload 50MB per file (PDF, DOCX, MD)
5. **Chunk Size**: 512 tokens, 50 token overlap (RecursiveCharacterTextSplitter)
6. **Embedding Dim**: 768 (nomic-embed-text)
7. **Guard Threshold**: relevance >= 0.4 cho Strict mode (vector cosine similarity; lowered from 0.7 since reranker unavailable, pipeline uses `vector_score` fallback)
