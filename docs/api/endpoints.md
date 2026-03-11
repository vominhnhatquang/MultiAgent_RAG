# API Contract - RAG Chatbot 10GB
## RESTful API + SSE Endpoints

**Author:** Alpha (System Architect)
**Version:** 1.0
**Base URL:** `http://localhost:8000/api/v1`

---

## 1. Overview

| Group | Prefix | Description |
|-------|--------|-------------|
| Health | `/health` | System health checks |
| Documents | `/documents` | Upload, list, delete documents |
| Chat | `/chat` | Chat with SSE streaming |
| Sessions | `/sessions` | Session management |
| Admin | `/admin` | Stats, reindex, memory |

---

## 2. Health Endpoints

### GET /health

Basic health check.

**Response 200:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-10T12:00:00Z"
}
```

### GET /health/detailed

Detailed health with service status and RAM usage.

**Response 200:**
```json
{
  "status": "healthy",
  "services": {
    "postgres": {"status": "up", "latency_ms": 2},
    "qdrant": {"status": "up", "latency_ms": 5, "collections": 1, "vectors_count": 12500},
    "redis": {"status": "up", "latency_ms": 1, "used_memory_mb": 45},
    "ollama": {"status": "up", "models_loaded": ["nomic-embed-text", "gemma2:2b"]}
  },
  "memory": {
    "total_gb": 10.0,
    "used_gb": 6.8,
    "available_gb": 3.2
  },
  "timestamp": "2026-03-10T12:00:00Z"
}
```

**Response 503 (service down):**
```json
{
  "status": "degraded",
  "services": {
    "postgres": {"status": "up"},
    "qdrant": {"status": "down", "error": "Connection refused"},
    "redis": {"status": "up"},
    "ollama": {"status": "up"}
  },
  "timestamp": "2026-03-10T12:00:00Z"
}
```

---

## 3. Document Endpoints

### POST /documents/upload

Upload a document for processing.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (required) - PDF, DOCX, MD, or TXT file (max 50MB)

**Response 202 Accepted:**
```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "report-2024.pdf",
  "file_type": "pdf",
  "file_size_bytes": 2457600,
  "status": "processing",
  "created_at": "2026-03-10T12:00:00Z"
}
```

**Error Responses:**

| Code | Condition | Body |
|------|-----------|------|
| 400 | No file provided | `{"error": "No file provided", "code": "MISSING_FILE"}` |
| 413 | File > 50MB | `{"error": "File too large. Maximum 50MB.", "code": "FILE_TOO_LARGE", "max_bytes": 52428800}` |
| 415 | Unsupported type | `{"error": "Unsupported file type: .xlsx", "code": "UNSUPPORTED_TYPE", "supported": ["pdf", "docx", "md", "txt"]}` |
| 409 | Duplicate file (same hash) | `{"error": "File already exists", "code": "DUPLICATE_FILE", "existing_doc_id": "..."}` |

### GET /documents

List all documents with pagination.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page (max 100) |
| status | string | null | Filter: processing, indexed, error |
| sort | string | created_at | Sort field |
| order | string | desc | asc or desc |

**Response 200:**
```json
{
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "report-2024.pdf",
      "file_type": "pdf",
      "file_size_bytes": 2457600,
      "status": "indexed",
      "chunk_count": 45,
      "created_at": "2026-03-10T12:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

### GET /documents/{doc_id}

Get single document details.

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "report-2024.pdf",
  "file_type": "pdf",
  "file_size_bytes": 2457600,
  "status": "indexed",
  "chunk_count": 45,
  "error_message": null,
  "created_at": "2026-03-10T12:00:00Z",
  "updated_at": "2026-03-10T12:00:30Z"
}
```

**Response 404:**
```json
{
  "error": "Document not found",
  "code": "NOT_FOUND",
  "doc_id": "550e8400-..."
}
```

### DELETE /documents/{doc_id}

Soft delete a document and its chunks.

**Response 200:**
```json
{
  "doc_id": "550e8400-...",
  "status": "deleted",
  "chunks_removed": 45
}
```

**Response 404:** Same as GET.

---

## 4. Chat Endpoints

### POST /chat

Send a chat message. Response is SSE stream.

**Request:**
- Content-Type: `application/json`

```json
{
  "session_id": "660e8400-e29b-41d4-a716-446655440000",
  "message": "Chi phi dao tao model nhu the nao?",
  "mode": "strict"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| session_id | UUID | No | auto-create | Chat session ID |
| message | string | Yes | - | User query (max 2000 chars) |
| mode | string | No | strict | "strict" or "general" |

**Response 200 (SSE Stream):**
```
Content-Type: text/event-stream

event: meta
data: {"session_id": "660e...", "model": "gemma2:2b", "mode": "strict"}

event: token
data: {"content": "Theo", "done": false}

event: token
data: {"content": " tai", "done": false}

event: token
data: {"content": " lieu", "done": false}

...

event: done
data: {"content": "", "done": true, "sources": [{"doc_id": "550e...", "filename": "report.pdf", "page": 5, "score": 0.85}], "model": "gemma2:2b", "total_tokens": 156}

event: error
data: {"error": "Generation timeout", "code": "TIMEOUT"}
```

**SSE Event Types:**

| Event | Description | Data Fields |
|-------|-------------|-------------|
| `meta` | Stream metadata (first event) | session_id, model, mode |
| `token` | Generated token | content, done |
| `sources` | Retrieved sources (after tokens) | sources[] |
| `done` | Stream complete | sources, model, total_tokens |
| `error` | Error during stream | error, code |
| `no_data` | Strict guard rejection | message |

**SSE `no_data` Event (Strict mode, no relevant docs):**
```
event: no_data
data: {"message": "Khong co thong tin lien quan trong tai lieu da upload.", "code": "NO_RELEVANT_DATA", "query": "Thoi tiet hom nay?"}
```

**Error Responses:**

| Code | Condition | Body |
|------|-----------|------|
| 400 | Empty message | `{"error": "Message cannot be empty", "code": "EMPTY_MESSAGE"}` |
| 400 | Message > 2000 chars | `{"error": "Message too long", "code": "MESSAGE_TOO_LONG", "max_chars": 2000}` |
| 404 | Session not found | `{"error": "Session not found", "code": "SESSION_NOT_FOUND"}` |
| 429 | Rate limit (> 10/min) | `{"error": "Rate limit exceeded", "code": "RATE_LIMIT", "retry_after": 30}` |
| 503 | Ollama unavailable | `{"error": "LLM service unavailable", "code": "LLM_UNAVAILABLE"}` |

---

## 5. Session Endpoints

### GET /sessions

List chat sessions.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page |
| tier | string | null | Filter: hot, warm, cold |

**Response 200:**
```json
{
  "sessions": [
    {
      "id": "660e8400-...",
      "title": "Chi phi dao tao model",
      "mode": "strict",
      "tier": "hot",
      "message_count": 8,
      "created_at": "2026-03-10T12:00:00Z",
      "updated_at": "2026-03-10T12:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 3,
    "total_pages": 1
  }
}
```

### GET /sessions/{session_id}

Get session with message history.

**Response 200:**
```json
{
  "id": "660e8400-...",
  "title": "Chi phi dao tao model",
  "mode": "strict",
  "tier": "hot",
  "message_count": 8,
  "messages": [
    {
      "id": "770e8400-...",
      "role": "user",
      "content": "Chi phi dao tao model nhu the nao?",
      "created_at": "2026-03-10T12:00:00Z"
    },
    {
      "id": "770e8401-...",
      "role": "assistant",
      "content": "Theo tai lieu report.pdf, trang 5...",
      "sources": [{"doc_id": "550e...", "filename": "report.pdf", "page": 5, "score": 0.85}],
      "model_used": "gemma2:2b",
      "created_at": "2026-03-10T12:00:03Z"
    }
  ],
  "created_at": "2026-03-10T12:00:00Z",
  "updated_at": "2026-03-10T12:30:00Z"
}
```

### PATCH /sessions/{session_id}

Update session title or mode.

**Request:**
```json
{
  "title": "Discussion about costs",
  "mode": "general"
}
```

**Response 200:**
```json
{
  "id": "660e8400-...",
  "title": "Discussion about costs",
  "mode": "general",
  "updated_at": "2026-03-10T12:35:00Z"
}
```

### DELETE /sessions/{session_id}

Delete a session and all its messages.

**Response 200:**
```json
{
  "session_id": "660e8400-...",
  "deleted": true,
  "messages_removed": 8
}
```

---

## 6. Feedback Endpoint

### POST /sessions/{session_id}/messages/{message_id}/feedback

Submit feedback for an assistant message.

**Request:**
```json
{
  "rating": "thumbs_up",
  "comment": "Accurate answer with good sources"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| rating | string | Yes | "thumbs_up" or "thumbs_down" |
| comment | string | No | Optional text feedback |

**Response 201:**
```json
{
  "id": "880e8400-...",
  "message_id": "770e8401-...",
  "rating": "thumbs_up",
  "created_at": "2026-03-10T12:35:00Z"
}
```

**Response 409 (already rated):**
```json
{
  "error": "Feedback already submitted for this message",
  "code": "DUPLICATE_FEEDBACK"
}
```

---

## 7. Admin Endpoints

### GET /admin/stats

System statistics.

**Response 200:**
```json
{
  "documents": {
    "total": 15,
    "indexed": 12,
    "processing": 2,
    "error": 1
  },
  "chunks": {
    "total": 3450,
    "avg_per_document": 287
  },
  "sessions": {
    "total": 25,
    "hot": 5,
    "warm": 15,
    "cold": 5,
    "active_last_hour": 3
  },
  "feedback": {
    "thumbs_up": 42,
    "thumbs_down": 8,
    "satisfaction_rate": 0.84
  },
  "models": {
    "loaded": ["nomic-embed-text", "gemma2:2b", "bge-reranker-v2"],
    "available": ["llama3.1:8b"]
  }
}
```

### POST /admin/reindex

Re-index all documents (rebuild Qdrant collection).

**Response 202:**
```json
{
  "task_id": "reindex-20260310-120000",
  "status": "started",
  "documents_to_process": 12
}
```

### GET /admin/memory

Current RAM usage breakdown.

**Response 200:**
```json
{
  "total_gb": 10.0,
  "used_gb": 6.8,
  "services": {
    "ollama": {"used_mb": 2400, "limit_mb": 6500},
    "postgres": {"used_mb": 650, "limit_mb": 800},
    "qdrant": {"used_mb": 500, "limit_mb": 800},
    "redis": {"used_mb": 45, "limit_mb": 300},
    "backend": {"used_mb": 280, "limit_mb": 500},
    "frontend": {"used_mb": 180, "limit_mb": 300}
  }
}
```

---

## 8. Common Response Patterns

### Error Response Format

All errors follow this structure:
```json
{
  "error": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE",
  "details": {}
}
```

### Error Codes Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| MISSING_FILE | 400 | No file in upload request |
| EMPTY_MESSAGE | 400 | Chat message is empty |
| MESSAGE_TOO_LONG | 400 | Message exceeds 2000 chars |
| INVALID_MODE | 400 | Mode not "strict" or "general" |
| NOT_FOUND | 404 | Resource does not exist |
| SESSION_NOT_FOUND | 404 | Session ID invalid |
| DUPLICATE_FILE | 409 | File already uploaded (hash match) |
| DUPLICATE_FEEDBACK | 409 | Already rated this message |
| FILE_TOO_LARGE | 413 | File exceeds 50MB limit |
| UNSUPPORTED_TYPE | 415 | File type not supported |
| RATE_LIMIT | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Unexpected server error |
| LLM_UNAVAILABLE | 503 | Ollama not responding |
| SERVICE_DOWN | 503 | Database or cache down |
| TIMEOUT | 504 | Generation or embedding timeout |
| NO_RELEVANT_DATA | - | Strict guard: no relevant docs (SSE event, not HTTP error) |

### Pagination Format

```json
{
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

---

## 9. CORS Configuration

```
Allowed Origins: ["http://localhost:3000"]
Allowed Methods: ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
Allowed Headers: ["Content-Type", "Authorization"]
Expose Headers: ["X-Request-ID"]
```

---

## 10. Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /chat | 10 requests | per minute per IP |
| POST /documents/upload | 5 requests | per minute per IP |
| All other | 60 requests | per minute per IP |
