# RAG Build Sprint — STATUS

**Phase:** 3/3 — ALL PHASES COMPLETE ✅
**Last Updated:** 2026-03-20 09:00
**Audit Score:** 57/60 (95%)
**Next Milestone:** Improvement Plan execution (Sprint 4-5)

---

## Overall Progress

| Phase | Description | Status | Date Completed |
|-------|-------------|--------|----------------|
| Phase 1 | Foundation — FastAPI + Qdrant + Ollama + Basic Chat | ✅ COMPLETE | 2026-03-10 |
| Phase 2 | Intelligence — HyDE + Rerank + Guard + Mode Switch | ✅ COMPLETE | 2026-03-19 |
| Phase 3 | Frontend — Next.js 14 Full UI + Admin Dashboard | ✅ COMPLETE | 2026-03-19 |
| Sprint 4-5 | Improvement Plan — Cold Tier + Celery + Rate Limit | 🔄 PLANNED | — |

---

## Phase 1 — COMPLETE ✅

| Exit Criterion | Result |
|----------------|--------|
| `docker-compose up` chạy được 7 services | ✅ PASS |
| Upload PDF → status "indexed" < 30s | ✅ PASS |
| Chat query → SSE stream từ gemma2 | ✅ PASS |
| End-to-end: upload doc A → hỏi → có nội dung doc A | ✅ PASS |
| RAM < 8GB (Phase 1, gemma2 only) | ✅ PASS |

---

## Phase 2 — COMPLETE ✅

| Exit Criterion | Result |
|----------------|--------|
| HyDE: implicit query → tìm đúng document | ✅ PASS |
| Hybrid BM25 + Vector + RRF (k=60) | ✅ PASS |
| Reranker: bge-reranker-v2-m3 cross-encoder | ✅ PASS |
| Strict Guard: irrelevant → "Không có thông tin" | ✅ PASS |
| Mode Switch: Strict ↔ General | ✅ PASS |
| Intent Classifier: chit-chat vs RAG | ✅ PASS |
| LLM Router: Ollama + Gemini fallback | ✅ PASS |
| Memory Tiers: Hot (Redis) + Warm (PG) | ✅ PASS |
| Ollama Scheduler: model swap gemma2 ↔ llama3.1 | ✅ PASS |
| RAM < 9GB normal operation | ✅ PASS |

**Partial items (deferred to improvement plan):**
- Cold tier storage (ADR-006) → improvement_plan.md A1
- Celery ingestion tasks (ADR-007) → improvement_plan.md A2

---

## Phase 3 — COMPLETE ✅

| Exit Criterion | Result |
|----------------|--------|
| Next.js 14 `npm run build` thành công | ✅ PASS |
| Chat interface: input + messages + SSE streaming | ✅ PASS |
| Mode Toggle: Strict ↔ General | ✅ PASS |
| Source Citations: expandable với score bar | ✅ PASS |
| Feedback Buttons: thumbs up/down + comment | ✅ PASS |
| Session Sidebar: grouped by date | ✅ PASS |
| Document Upload: drag-drop + progress + list | ✅ PASS |
| Admin Dashboard: stats, memory, services, models | ✅ PASS |
| Responsive: mobile sidebar (Sheet overlay) | ✅ PASS |
| Toast Notifications: sonner integration | ✅ PASS |

**Known issues (tracked in improvement plan):**
- `frontend/lib/api.ts:97-98` — wildcard `*` in feedback path → A3
- Admin API endpoints not yet in backend → B2

---

## Agent Status Board

| Agent | Phase 1 | Phase 2 | Phase 3 | Current Assignment |
|-------|---------|---------|---------|-------------------|
| Alpha | ✅ Done | ✅ Reviewed | ✅ Reviewed | Improvement plan oversight |
| Beta | ✅ Done | ✅ Done | — | A1 Cold Tier, A2 Celery, B2 Admin API, B3 Rate Limit |
| Delta | ✅ Done | — | ✅ Done | A3 Fix Feedback Path, C2 Error Boundaries |
| Epsilon | ✅ Done | ✅ Done | — | B1 Celery Beat Container |

---

## Handoff Log — ALL ACCEPTED

| Handoff | File | Phase | Accepted |
|---------|------|-------|----------|
| Alpha → Beta | `completed/alpha-to-beta-2026-03-10.json` | 1 | ✅ 2026-03-10 |
| Alpha → Epsilon | `completed/alpha-to-epsilon-2026-03-10.json` | 1 | ✅ 2026-03-10 |
| Alpha → Delta | `completed/alpha-to-delta-2026-03-10.json` | 1 | ✅ 2026-03-10 |
| Delta → Orchestrator | `completed/delta-complete-2026-03-10.json` | 1 | ✅ 2026-03-10 |
| Beta → Delta | `completed/beta-to-delta-phase2-2026-03-19.json` | 2 | ✅ 2026-03-20 |
| Delta → Orchestrator | `completed/delta-phase3-complete-2026-03-19.json` | 3 | ✅ 2026-03-20 |

---

## Improvement Plan Status (Sprint 4-5)

| ID | Task | Agent | Priority | Status |
|----|------|-------|----------|--------|
| A1 | Cold Tier Storage (ADR-006) | Beta | HIGH | ⬜ Not started |
| A2 | Celery Document Ingestion (ADR-007) | Beta | HIGH | ⬜ Not started |
| A3 | Fix Frontend Feedback API Path | Delta | MEDIUM | ⬜ Not started |
| B1 | Celery Beat Container | Epsilon | MEDIUM | ⬜ Not started |
| B2 | Admin API Endpoints | Beta | MEDIUM | ⬜ Not started |
| B3 | Rate Limiting Middleware | Beta | MEDIUM | ⬜ Not started |
| C1 | Integration Tests | Beta | LOW | ⬜ Not started |
| C2 | Error Boundaries + Loading States | Delta | LOW | ⬜ Not started |
| C3 | Session PATCH Endpoint | Beta | LOW | ⬜ Not started |

**Target:** Audit score 57/60 → 60/60, Test coverage 60% → 80%

---

## Architecture Decisions

| ID | Decision | Status |
|----|----------|--------|
| ADR-001 | Qdrant primary + pgvector backup | ✅ Implemented |
| ADR-002 | Ollama swap strategy (MAX_LOADED=1) | ✅ Implemented |
| ADR-003 | Gemini API fallback | ✅ Implemented |
| ADR-004 | Hybrid BM25 + Vector + RRF (k=60) | ✅ Implemented |
| ADR-005 | SSE streaming | ✅ Implemented |
| ADR-006 | 3-tier Hot/Warm/Cold | ⚠️ Partial (Cold missing) |
| ADR-007 | Celery + Redis task queue | ⚠️ Partial (only health_check) |
| ADR-008 | bge-reranker-v2 sentence-transformers | ✅ Implemented |
| ADR-009 | HyDE 0.7/0.3 weighting | ✅ Implemented |

---

## Tech Stack

| Component | Technology | Container | RAM Limit |
|-----------|-----------|-----------|-----------|
| Backend API | FastAPI (Python 3.12) | rag_backend | 700 MB |
| Task Queue | Celery + Redis | rag_celery | 200 MB |
| Frontend | Next.js 14 (App Router) | rag_frontend | 200 MB |
| Database | PostgreSQL 16 + pgvector | rag_postgres | 800 MB |
| Vector DB | Qdrant v1.9.0 | rag_qdrant | 800 MB |
| Cache | Redis 7.2 Alpine | rag_redis | 300 MB |
| LLM Runtime | Ollama (gemma2:2b default) | rag_ollama | 6100 MB |
| **Total** | | **7 containers** | **9100 MB** |

---

## RAM Budget

| State | RAM | Headroom |
|-------|-----|----------|
| Phase 1 normal | 5.7 GB | 4.3 GB |
| Phase 2 normal | 6.6 GB | 3.4 GB |
| Phase 3 normal | 6.6 GB | 3.4 GB |
| Phase 3 peak (swap llama3.1) | 9.5 GB | 0.5 GB |
