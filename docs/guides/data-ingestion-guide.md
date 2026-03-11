# Hướng Dẫn: Luồng Xử Lý Dữ Liệu — Từ Upload Đến Database

**Dành cho:** Developer, DevOps, QA
**Phiên bản:** Phase 1 (sync ingestion, không Celery)

---

## Tổng Quan

Có **2 cách đưa dữ liệu vào hệ thống**:

| Cách | Mô tả | Khi nào dùng |
|------|-------|-------------|
| **API Upload** | `POST /api/v1/documents/upload` | Upload trực tiếp từ UI hoặc script |
| **File Drop** | Đặt file vào `data/uploads/raw/` | Batch import, migration dữ liệu |

Dù đi theo cách nào, **pipeline xử lý đều giống nhau** từ bước Extract trở đi.

---

## Sơ Đồ Tổng Thể

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NGUỒN DỮ LIỆU                               │
│                                                                     │
│   [Browser/Client]              [Filesystem]                        │
│   POST /api/v1/documents/upload  data/uploads/raw/file.pdf          │
└───────────────┬─────────────────────────┬───────────────────────────┘
                │                         │
                ▼                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BƯỚC 0 — VALIDATE & REGISTER                                        │
│                                                                      │
│  • Kiểm tra kích thước ≤ 50MB                                        │
│  • Kiểm tra định dạng: pdf | docx | md | txt                         │
│  • Tính SHA-256 hash → kiểm tra trùng lặp trong PostgreSQL           │
│  • INSERT document (status = "processing") vào bảng documents        │
│  • Trả về 202 Accepted + doc_id cho client                           │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ file_bytes + doc_id
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BƯỚC 1 — EXTRACT (app/core/ingestion/extractor.py)                 │
│                                                                      │
│  PDF  → PyMuPDF (fitz): mỗi trang → ExtractedPage(page_number, text)│
│  DOCX → python-docx: ghép các paragraph → 1 trang                   │
│  MD/TXT → đọc UTF-8 thô → 1 trang                                   │
│                                                                      │
│  Output: ExtractedDocument { pages: [ExtractedPage, ...] }           │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ ExtractedDocument
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BƯỚC 2 — CLEAN (app/core/ingestion/cleaner.py)                     │
│                                                                      │
│  • Unicode NFC normalization (é = é, không phải e + combining mark)  │
│  • Xoá control characters (\x00–\x1f trừ \n \t)                     │
│  • Xoá dòng chỉ chứa số trang (e.g. "42" một mình)                  │
│  • Collapse khoảng trắng thừa (tab, double space)                    │
│  • Collapse xuống dòng liên tiếp (≥3 \n → \n\n)                     │
│  • Loại bỏ trang trống sau khi clean                                 │
│                                                                      │
│  Output: ExtractedDocument (đã clean, pages rỗng bị loại bỏ)        │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ Cleaned ExtractedDocument
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BƯỚC 3 — CHUNK (app/core/ingestion/chunker.py)                     │
│                                                                      │
│  • Tách văn bản thành câu dựa trên dấu chấm câu (. ! ? \n)          │
│  • Gom câu vào buffer, giới hạn 512 tokens (tiktoken cl100k_base)   │
│  • Khi buffer đầy → tạo chunk, giữ lại 64 tokens phần overlap        │
│  • Câu đơn > 512 tokens → tách theo từ                              │
│                                                                      │
│  Mỗi TextChunk gồm:                                                  │
│    content       : nội dung văn bản                                  │
│    chunk_index   : thứ tự (0, 1, 2, ...)                            │
│    page_number   : trang gốc trong tài liệu                          │
│    token_count   : số token thực tế                                  │
│    char_count    : số ký tự                                          │
│                                                                      │
│  Output: List[TextChunk]                                             │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ List[TextChunk]
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BƯỚC 4 — ENRICH (app/core/ingestion/enricher.py)                   │
│                                                                      │
│  • Phát hiện ngôn ngữ: vi (có dấu tiếng Việt) | en (còn lại)        │
│  • Trích xuất 5 từ khoá quan trọng nhất (tần suất, loại bỏ stopword) │
│  • Ghi vào chunk.metadata dict                                       │
│                                                                      │
│  metadata sau bước này:                                              │
│    { "language": "vi", "keywords": ["chi phí", "đào tạo", ...] }    │
│                                                                      │
│  Output: List[TextChunk] (metadata được bổ sung)                    │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ List[TextChunk] (enriched)
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BƯỚC 5 — EMBED (app/core/ingestion/embedder.py)                    │
│                                                                      │
│  • Gửi nội dung chunk tới Ollama theo batch (16 chunks/request)      │
│  • Endpoint: POST http://localhost:11434/api/embed                   │
│  • Model: nomic-embed-text (768 dimensions, ~0.3GB RAM)              │
│  • Ollama trả về vector float32[768] cho mỗi chunk                   │
│                                                                      │
│  Output: List[(TextChunk, List[float])]  — cặp (chunk, vector)      │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ List[(TextChunk, vector)]
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BƯỚC 6 — INDEX (app/core/ingestion/indexer.py)                     │
│                                                                      │
│  ┌─────────────────────────────┐  ┌───────────────────────────────┐  │
│  │       PostgreSQL            │  │           Qdrant              │  │
│  │                             │  │                               │  │
│  │  INSERT INTO chunks:        │  │  Upsert PointStruct:          │  │
│  │    id          = UUID       │  │    id      = str(chunk_id)    │  │
│  │    document_id = doc_id     │  │    vector  = float32[768]     │  │
│  │    content     = text       │  │    payload = {                │  │
│  │    chunk_index = N          │  │      doc_id, filename,        │  │
│  │    page_number = P          │  │      chunk_index, page_number,│  │
│  │    token_count = T          │  │      language, content        │  │
│  │    char_count  = C          │  │    }                          │  │
│  │    metadata    = JSONB      │  │                               │  │
│  │                             │  │  Collection: document_chunks  │  │
│  │  UPDATE documents SET       │  │  Distance: Cosine             │  │
│  │    status = "indexed"       │  │  Quantization: int8           │  │
│  │    chunk_count = N          │  │                               │  │
│  └─────────────────────────────┘  └───────────────────────────────┘  │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  HOÀN THÀNH                                                          │
│                                                                      │
│  • GET /api/v1/documents/{doc_id} → status: "indexed"                │
│  • Chunk có thể tìm kiếm qua POST /api/v1/chat                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Cách 1: Upload Qua API

### Request

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@/path/to/report.pdf"
```

### Response 202 (ngay lập tức)

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "report.pdf",
  "file_type": "pdf",
  "file_size_bytes": 2457600,
  "status": "processing",
  "created_at": "2026-03-11T08:00:00Z"
}
```

> **Phase 1 lưu ý:** Pipeline chạy **đồng bộ** trong request. Response 202 được trả về ngay sau khi document được tạo trong DB, nhưng connection vẫn giữ open cho đến khi pipeline xong. Phase 2 sẽ chuyển sang Celery async.

### Kiểm tra trạng thái

```bash
curl http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000
```

```json
{
  "id": "550e8400-...",
  "status": "indexed",
  "chunk_count": 45,
  "updated_at": "2026-03-11T08:00:28Z"
}
```

---

## Cách 2: Đặt File Vào `data/uploads/raw/`

Dành cho batch import hoặc khi không muốn dùng API.

### Cấu trúc thư mục

```
data/
└── uploads/
    ├── raw/          ← Đặt file vào đây
    └── processed/    ← File được move sang đây sau khi xử lý
```

### Chạy script import thủ công

```bash
# Đặt file
cp ~/documents/report.pdf data/uploads/raw/

# Gọi API để trigger import (Phase 1)
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@data/uploads/raw/report.pdf"

# Hoặc dùng script batch (nếu có nhiều file)
for f in data/uploads/raw/*.pdf; do
  echo "Uploading $f ..."
  curl -s -X POST http://localhost:8000/api/v1/documents/upload \
    -F "file=@$f" | jq '.doc_id'
done
```

> **Phase 2:** Sẽ có watcher service tự động phát hiện file mới trong `raw/` và trigger ingestion pipeline, sau đó move sang `processed/`.

---

## Chi Tiết Từng Bước

### Bước 0 — Validate & Register

**File:** [app/api/v1/documents.py](../../backend/app/api/v1/documents.py)

| Kiểm tra | Giá trị | Lỗi trả về |
|----------|---------|-----------|
| Có file không | — | `400 MISSING_FILE` |
| Định dạng | pdf, docx, md, txt | `415 UNSUPPORTED_TYPE` |
| Kích thước | ≤ 50MB | `413 FILE_TOO_LARGE` |
| Trùng nội dung | SHA-256 hash | `409 DUPLICATE_FILE` |

Sau validate → INSERT vào bảng `documents`:

```sql
INSERT INTO documents (filename, file_type, file_size_bytes, file_hash, status)
VALUES ('report.pdf', 'pdf', 2457600, 'abc123...', 'processing');
```

---

### Bước 1 — Extract

**File:** [app/core/ingestion/extractor.py](../../backend/app/core/ingestion/extractor.py)

| Định dạng | Thư viện | Đặc điểm |
|----------|---------|---------|
| PDF | `pymupdf` (fitz) | Giữ nguyên `page_number` từng trang |
| DOCX | `python-docx` | Ghép tất cả paragraph, page = 1 |
| MD / TXT | built-in | Đọc UTF-8, page = 1 |

**Ví dụ output:**
```python
ExtractedDocument(pages=[
    ExtractedPage(page_number=1, text="Chương 1: Giới thiệu\n..."),
    ExtractedPage(page_number=2, text="Chi phí đào tạo bao gồm..."),
])
```

---

### Bước 2 — Clean

**File:** [app/core/ingestion/cleaner.py](../../backend/app/core/ingestion/cleaner.py)

**Trước clean:**
```
Chi   phí  đào  tạo\x00\n\n\n\n42\n\nBao gồm...
```

**Sau clean:**
```
Chi phí đào tạo

Bao gồm...
```

---

### Bước 3 — Chunk

**File:** [app/core/ingestion/chunker.py](../../backend/app/core/ingestion/chunker.py)

**Tham số (cấu hình qua `.env`):**

| Tham số | Mặc định | Ý nghĩa |
|---------|---------|--------|
| `CHUNK_SIZE` | 512 | Token tối đa mỗi chunk |
| `CHUNK_OVERLAP` | 64 | Token overlap giữa chunks liên tiếp |

**Ví dụ:** Văn bản 1000 tokens → ~2–3 chunks có overlap 64 tokens.

**Cơ chế overlap** đảm bảo ngữ cảnh không bị cắt đứt tại ranh giới chunk:

```
Chunk 0: [token 1 ... token 512]
Chunk 1: [token 449 ... token 960]   ← 64 tokens overlap từ chunk 0
Chunk 2: [token 897 ... token 1000]  ← 64 tokens overlap từ chunk 1
```

---

### Bước 4 — Enrich

**File:** [app/core/ingestion/enricher.py](../../backend/app/core/ingestion/enricher.py)

Metadata được ghi vào `chunk.metadata` (JSONB trong PostgreSQL):

```json
{
  "language": "vi",
  "keywords": ["chi phí", "đào tạo", "mô hình", "ngân sách", "triệu"]
}
```

---

### Bước 5 — Embed

**File:** [app/core/ingestion/embedder.py](../../backend/app/core/ingestion/embedder.py)

```
Ollama API: POST http://localhost:11434/api/embed
Body: {
  "model": "nomic-embed-text",
  "input": ["chunk text 1", "chunk text 2", ...]   ← batch 16 chunks
}
Response: {
  "embeddings": [[0.012, -0.034, ...], ...]        ← float32[768] × N
}
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Cách xử lý |
|-----|------------|-----------|
| `503 LLM_UNAVAILABLE` | Ollama chưa chạy | `ollama serve` |
| `404 model not found` | Model chưa pull | `ollama pull nomic-embed-text` |
| Timeout | File quá lớn, batch quá nhiều | Giảm `EMBED_BATCH_SIZE` |

---

### Bước 6 — Index

**File:** [app/core/ingestion/indexer.py](../../backend/app/core/ingestion/indexer.py)

**PostgreSQL** — bảng `chunks`:
```sql
INSERT INTO chunks (id, document_id, content, chunk_index, page_number,
                    token_count, char_count, metadata)
VALUES ('uuid', 'doc-uuid', 'Chi phí đào tạo...', 0, 2, 87, 412,
        '{"language":"vi","keywords":["chi phí"]}');
```

**Qdrant** — collection `document_chunks`:
```json
{
  "id": "chunk-uuid",
  "vector": [0.012, -0.034, 0.891, ...],
  "payload": {
    "doc_id": "doc-uuid",
    "filename": "report.pdf",
    "chunk_index": 0,
    "page_number": 2,
    "language": "vi",
    "content": "Chi phí đào tạo bao gồm..."
  }
}
```

**Cập nhật document:**
```sql
UPDATE documents
SET status = 'indexed', chunk_count = 45
WHERE id = 'doc-uuid';
```

---

## Xử Lý Lỗi Trong Pipeline

Nếu bất kỳ bước nào thất bại:

```sql
UPDATE documents
SET status = 'error',
    error_message = 'PyMuPDF failed: encrypted PDF'
WHERE id = 'doc-uuid';
```

Client kiểm tra:
```bash
curl http://localhost:8000/api/v1/documents/{doc_id}
# → { "status": "error", "error_message": "PyMuPDF failed: encrypted PDF" }
```

**Trạng thái vòng đời của document:**

```
processing → indexed    (thành công)
processing → error      (pipeline thất bại)
indexed    → deleted    (soft delete qua API)
```

---

## Kiểm Tra Dữ Liệu Sau Ingestion

### PostgreSQL

```bash
# Kết nối
docker exec -it rag-postgres psql -U raguser -d ragdb

# Kiểm tra document
SELECT id, filename, status, chunk_count FROM documents;

# Kiểm tra chunks
SELECT id, chunk_index, page_number, token_count, char_count
FROM chunks
WHERE document_id = 'your-doc-id'
ORDER BY chunk_index;

# Đọc nội dung chunk
SELECT content FROM chunks WHERE document_id = 'your-doc-id' AND chunk_index = 0;
```

### Qdrant

```bash
# Kiểm tra số vector trong collection
curl http://localhost:6333/collections/document_chunks

# Tìm kiếm thử (vector giả)
curl -X POST http://localhost:6333/collections/document_chunks/points/search \
  -H 'Content-Type: application/json' \
  -d '{
    "vector": [0.1, 0.2, ...],
    "limit": 3,
    "with_payload": true
  }'
```

### Kiểm tra qua API

```bash
# List tất cả documents
curl http://localhost:8000/api/v1/documents

# Chi tiết document
curl http://localhost:8000/api/v1/documents/{doc_id}

# Test chat với document vừa upload
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Tóm tắt nội dung tài liệu", "mode": "strict"}' \
  --no-buffer
```

---

## Khởi Động Backend

Có **2 cách chạy** tuỳ theo môi trường:

---

### Cách A — Standalone Script (không cần Docker)

Dùng khi Docker/PostgreSQL chưa sẵn sàng. Chỉ cần **Ollama** đang chạy.

```bash
# 1. Đảm bảo Ollama đang chạy (nếu chưa)
ollama serve &

# 2. Pull models nếu chưa có
ollama pull nomic-embed-text
ollama pull gemma2:2b

# 3. Cài Python dependencies (chỉ cần 1 lần)
pip install pymupdf tiktoken httpx structlog --break-system-packages

# 4. Đặt file PDF vào raw dir
cp /path/to/file.pdf data/uploads/raw/

# 5. Chạy pipeline (xử lý tất cả file trong raw/)
cd /mnt/workspace/Project_RAG/rag-chatbot
python3 scripts/ingest_local.py

# Chỉ xử lý 1 file cụ thể
python3 scripts/ingest_local.py --file data/uploads/raw/report.pdf
```

**Output được lưu tại:**
```
data/processed/
├── chunks.db            ← SQLite: metadata + nội dung chunks
├── vectors.jsonl        ← Vectors 768-dim từ nomic-embed-text
└── ingestion_summary.json
```

**Kiểm tra kết quả:**
```bash
# Xem danh sách documents đã indexed
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/processed/chunks.db')
for row in conn.execute('SELECT filename, status, chunk_count FROM documents'):
    print(f'{row[0]:<50} {row[1]}  {row[2]} chunks')
"

# Đếm tổng số vectors
wc -l data/processed/vectors.jsonl
```

---

### Cách B — Full Backend với Docker (production)

Dùng khi Docker Desktop / Docker Engine đang chạy.

```bash
# 1. Kiểm tra Docker daemon
docker ps

# 2. Copy file .env (nếu chưa có)
cp .env.example .env
# Sửa các giá trị nếu cần (mặc định đã hoạt động cho local dev)

# 3. Khởi động tất cả services
docker compose up -d postgres redis qdrant

# Chờ services healthy (khoảng 15-30s)
docker compose ps

# 4. Build và khởi động backend
docker compose up -d backend

# 5. Chạy database migrations
docker compose exec backend alembic upgrade head
```

**Kiểm tra backend đang chạy:**
```bash
curl http://localhost:8000/health
# → {"status": "ok", "version": "0.1.0"}

curl http://localhost:8000/docs
# → Swagger UI (mở trên trình duyệt)
```

**Upload và xử lý file:**
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@data/uploads/raw/report.pdf"
```

---

### Cách C — Dev Mode với uv (không cần Docker, không cần PostgreSQL)

Dùng khi muốn chạy backend đầy đủ trên máy local, không có Docker.
Tự động dùng: **SQLite** thay PostgreSQL, **in-memory Qdrant**, **fakeredis**.

#### Yêu cầu
- `uv` đã cài: `curl -LsSf https://astral.sh/uv | sh`
- Ollama đang chạy với model `nomic-embed-text` và `gemma2:2b`

#### Khởi động lần đầu

```bash
cd /path/to/rag-chatbot

# 1. Tạo virtual environment với uv
uv venv backend/.venv --python 3.12

# 2. Cài tất cả dependencies vào venv
uv pip install --python backend/.venv/bin/python \
  fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg alembic \
  "redis[hiredis]" fakeredis httpx pydantic pydantic-settings python-multipart \
  qdrant-client structlog psutil pymupdf python-docx tiktoken \
  celery google-genai aiosqlite

# 3. File .env.dev đã có sẵn (dev_mode=true, SQLite, in-memory Qdrant, fakeredis)
# Xem: backend/.env.dev

# 4. Khởi động backend (tự tạo bảng SQLite, không cần alembic)
cd backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Các lần sau (backend đã setup)

```bash
cd /path/to/rag-chatbot/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Kiểm tra backend đang chạy

```bash
curl http://localhost:8000/health
# → {"status": "healthy", "timestamp": "..."}

curl http://localhost:8000/docs
# → Swagger UI (mở trên trình duyệt)
```

#### Upload và xử lý file PDF

```bash
# Upload 1 file
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@data/uploads/raw/report.pdf"

# Batch upload tất cả file trong raw/
for f in data/uploads/raw/*.pdf; do
  echo "Uploading $(basename $f)..."
  curl -s -X POST http://localhost:8000/api/v1/documents/upload \
    -F "file=@$f" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f\"  {d.get('filename','?')}: {d.get('status','?')} ({d.get('chunk_count','?')} chunks)\")
" 2>/dev/null || echo "  done"
done

# Kiểm tra tất cả documents
curl -s http://localhost:8000/api/v1/documents | python3 -c "
import json, sys
for d in json.load(sys.stdin)['documents']:
    print(f\"{d['filename']:<50} {d['status']:<10} {d.get('chunk_count',0)} chunks\")
"
```

#### Test chat sau khi upload

```bash
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What modules does the system have?", "mode": "strict"}' \
  --no-buffer
```

> **Lưu ý Dev Mode:**
> - Dữ liệu Qdrant (vectors) và SQLite (`backend/dev.db`) mất khi restart server
> - Upload lại file sau mỗi lần restart
> - Dùng Cách B (Docker) hoặc Cách C với PostgreSQL thật cho persistent storage

#### Cách C với PostgreSQL thật (production-like)

```bash
# Sau khi cài PostgreSQL, Redis, Qdrant native:
# Xoá .env.dev để tắt dev mode (hoặc đặt DEV_MODE=false)
rm backend/.env.dev   # hoặc đặt DEV_MODE=false

# Cấu hình .env
cat > backend/.env << 'EOF'
POSTGRES_HOST=localhost
POSTGRES_USER=raguser
POSTGRES_PASSWORD=ragpass
POSTGRES_DB=ragdb
REDIS_HOST=localhost
QDRANT_HOST=localhost
OLLAMA_BASE_URL=http://localhost:11434
SECRET_KEY=your-secret-key-here
EOF

# Chạy migrations
cd backend && .venv/bin/alembic upgrade head

# Khởi động
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Yêu Cầu Dịch Vụ Phải Chạy

| Service | Cách A (Standalone) | Cách B (Docker) | Cách C (Native) |
|---------|-------------------|-----------------|-----------------|
| Ollama | ✓ Bắt buộc | ✓ Bắt buộc | ✓ Bắt buộc |
| PostgreSQL | ✗ Không cần | ✓ Docker | ✓ Native |
| Qdrant | ✗ Không cần | ✓ Docker | ✓ Native |
| Redis | ✗ Không cần | Optional | Optional |

```bash
# Kiểm tra Ollama và models
curl http://localhost:11434/api/tags | python3 -c "
import json, sys
models = [m['name'] for m in json.load(sys.stdin).get('models', [])]
print('Models:', models)
for m in ['nomic-embed-text', 'gemma2:2b']:
    status = '✓' if any(m in x for x in models) else '✗ MISSING'
    print(f'  {m}: {status}')
"

# Pull nếu chưa có
ollama pull nomic-embed-text
ollama pull gemma2:2b
```

---

## Ước Tính Thời Gian Xử Lý (Phase 1)

| Kích thước tài liệu | Số chunk ước tính | Thời gian embed | Tổng |
|--------------------|------------------|----------------|------|
| 10 trang PDF (~50KB) | ~15 chunks | ~3s | ~5s |
| 50 trang PDF (~250KB) | ~75 chunks | ~15s | ~20s |
| 200 trang PDF (~1MB) | ~300 chunks | ~60s | ~75s |

> Thời gian phụ thuộc vào tốc độ CPU của máy chạy Ollama.
