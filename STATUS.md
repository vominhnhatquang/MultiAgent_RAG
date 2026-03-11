# RAG Build Sprint - STATUS

**Phase:** 2/3 (Intelligence — HyDE + Rerank + Strict Guard)
**Last Updated:** 2026-03-11 00:00
**Previous Milestone:** Phase 1 Demo — PASSED ✅
**Next Milestone:** Phase 2 Demo

---

## Phase 1 — COMPLETE ✅

| Exit Criterion | Result |
|----------------|--------|
| `docker-compose up` chạy được 3 services | ✅ PASS |
| Upload PDF → status "indexed" < 30s | ✅ PASS |
| Chat query → SSE stream từ gemma2 | ✅ PASS |
| End-to-end: upload doc A → hỏi → có nội dung doc A | ✅ PASS |
| RAM < 8GB (Phase 1, gemma2 only) | ✅ PASS |

---

## Agent Status Board

| Agent | Phase 1 | Current Task (Phase 2) | Status | Blocker |
|-------|---------|------------------------|--------|---------|
| Alpha | ✅ Done | Update API Contract v2 (mode switch + HyDE metadata) | Ready | — |
| Beta | ✅ Done | HyDE + Hybrid Search + Reranker + Strict Guard | Waiting Alpha v2 | — |
| Delta | ✅ Done | Mode Switch Toggle + Source Citation UI | Waiting Alpha v2 | — |
| Epsilon | ✅ Done | Add Redis + OLLAMA_KEEP_ALIVE + health scripts | Ready to start | — |

---

## Phase 1 Handoff Log — ALL ACCEPTED

| Handoff | File | Accepted |
|---------|------|----------|
| Alpha → Beta | `completed/alpha-to-beta-2026-03-10.json` | ✅ 2026-03-10 |
| Alpha → Epsilon | `completed/alpha-to-epsilon-2026-03-10.json` | ✅ 2026-03-10 |
| Alpha → Delta | `completed/alpha-to-delta-2026-03-10.json` | ✅ 2026-03-10 |
| Delta → Orchestrator | `completed/delta-complete-2026-03-10.json` | ✅ 2026-03-10 |

---

## Phase 1 Deliverables (frozen)

**Alpha (Architecture):**
- [x] `docs/architecture/system-overview.md`
- [x] `docs/architecture/data-flow.md`
- [x] `docs/architecture/memory-budget-10gb.md`
- [x] `docs/architecture/tech-decisions.md` (9 ADRs)
- [x] `docs/schemas/database-schema.sql`
- [x] `docs/schemas/qdrant-collection.json`
- [x] `docs/schemas/erd.md`
- [x] `docs/api/endpoints.md`
- [x] `agents/shared/contracts/API_CONTRACT.md`
- [x] `agents/shared/schemas/DATABASE_SCHEMA.md`

**Beta (Backend):**
- [x] FastAPI app + `/health`, `/documents/upload`, `/chat` (SSE)
- [x] Document pipeline: extract → chunk → embed (nomic) → index (Qdrant)
- [x] Basic vector search + gemma2 generation + SSE streaming

**Delta (Frontend):**
- [x] Next.js 14 port 3000: sidebar, chat area, upload page
- [x] SSE streaming (fetch + ReadableStream)
- [x] hooks: useChat, useSession, useUpload

**Epsilon (DevOps):**
- [x] docker-compose.yml: postgres, qdrant, ollama, backend, frontend
- [x] PostgreSQL 16 + pgvector enabled
- [x] Ollama: nomic-embed-text + gemma2:2b pulled
- [x] Memory limits per memory-budget-10gb.md

---

## Phase 2 — In Progress

### Alpha (Next)
- [ ] Update `API_CONTRACT.md` v2: mode switch, sources SSE format
- [ ] Update schema: `metadata JSONB` cho chunks, BM25 GIN index
- [ ] Create phase2 handoff files cho Beta + Delta

### Beta (Waiting Alpha v2)
- [ ] `core/retrieval/query_transformer.py` — HyDE (gemma2, 100 tok)
- [ ] `core/retrieval/hybrid_search.py` — BM25 + Vector + RRF (k=60)
- [ ] `core/retrieval/reranker.py` — bge-reranker-v2 (sentence-transformers)
- [ ] `core/generation/guard.py` — Strict Guard (threshold 0.7)
- [ ] `core/generation/intent_classifier.py` — Chit-chat vs RAG
- [ ] `core/generation/llm_router.py` — Easy/Hard/Offline routing

### Delta (Waiting Alpha v2)
- [ ] `components/sidebar/ModeToggle.tsx` — Strict ↔ General
- [ ] `components/chat/SourceCitation.tsx` — expandable sources
- [ ] Hiển thị `sources` từ SSE `done` event

### Epsilon (Independent — start now)
- [ ] Thêm Redis container (300MB, allkeys-lru)
- [ ] OLLAMA_KEEP_ALIVE=5m, OLLAMA_NUM_PARALLEL=2
- [ ] `infra/scripts/health-check.sh`
- [ ] `infra/monitoring/check_ram.py`

---

## Phase 2 Exit Criteria

- [ ] Strict mode: "Thời tiết hôm nay?" → "Không có thông tin trong tài liệu"
- [ ] HyDE: "so sánh chi phí" (implicit) → tìm đúng bảng giá
- [ ] Toggle Strict/General → behavior thay đổi đúng
- [ ] Model swap: offline + hard query → llama3.1 load (no OOM)
- [ ] RAM < 9GB trong Phase 2 normal operation

---

## Architecture Decisions

| ID | Decision | Phase |
|----|----------|-------|
| ADR-001 | Qdrant primary + pgvector backup | Locked |
| ADR-002 | Ollama swap strategy | Locked |
| ADR-003 | Gemini API free tier | Locked |
| ADR-004 | Hybrid BM25 + Vector + RRF | **Phase 2** |
| ADR-005 | SSE streaming | Locked |
| ADR-006 | 3-tier Hot/Warm/Cold | Phase 3 |
| ADR-007 | Celery + Redis | **Phase 2 (Redis)** |
| ADR-008 | bge-reranker-v2 | **Phase 2** |
| ADR-009 | HyDE 0.7/0.3 | **Phase 2** |

---

## RAM Budget

| State | RAM | Headroom |
|-------|-----|----------|
| Phase 1 normal | 5.7 GB | 4.3 GB |
| Phase 2 normal | 6.6 GB | 3.4 GB |
| Phase 3 normal | 6.6 GB | 3.4 GB |
| Phase 3 peak (swap) | 9.5 GB | 0.5 GB |
