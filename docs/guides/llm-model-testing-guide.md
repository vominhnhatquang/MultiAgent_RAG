# Hướng Dẫn: Kiểm Tra Docker Services & Test 3 LLM Models

**Models:** gemma2:2b · llama3.1:8b · Gemini 1.5 Flash
**Modes:** Dev Mode (SQLite/fakeredis/in-memory Qdrant) · Docker Mode (PostgreSQL/Redis/Qdrant thật)

---

## Tổng Quan: 2 Chế Độ Hoạt Động

```
┌─────────────────────────────────────────────────────────────────┐
│  DEV_MODE=true  (backend/.env.dev)                              │
│  ├── DB      → SQLite   (dev.db, không cần Docker)              │
│  ├── Cache   → fakeredis (in-process, không cần Docker)         │
│  ├── Vector  → Qdrant in-memory (không cần Docker)              │
│  └── LLM     → Ollama localhost:11434 hoặc Gemini API           │
├─────────────────────────────────────────────────────────────────┤
│  DEV_MODE=false  (docker-compose.yml)                           │
│  ├── DB      → PostgreSQL container (port 5432)                 │
│  ├── Cache   → Redis container (port 6379)                      │
│  ├── Vector  → Qdrant container (port 6333)                     │
│  └── LLM     → Ollama container (port 11434) hoặc Gemini API    │
└─────────────────────────────────────────────────────────────────┘
```

---

## PHẦN A — Dev Mode (Không Cần Docker)

> Phù hợp khi test nhanh, không cần cài đặt phức tạp.

### A.1 Điều Kiện Tiên Quyết

```bash
# 1. Kiểm tra Ollama đang chạy và có models
curl -s http://localhost:11434/api/tags | python3 -c "
import json, sys
models = json.load(sys.stdin).get('models', [])
for m in models:
    print(' -', m['name'])
print('Total:', len(models), 'models')
"
# Phải thấy: gemma2:2b, llama3.1:8b, nomic-embed-text

# Pull nếu chưa có
ollama pull gemma2:2b
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# 2. Kiểm tra venv
ls rag-chatbot/backend/.venv/bin/uvicorn
# Nếu chưa có → xem docs/guides/data-ingestion-guide.md
```

### A.2 Quy Trình Dev Mode

```
[1] Ollama đang chạy
        ↓
[2] Sửa backend/.env.dev → chọn model
        ↓
[3] Khởi động uvicorn (DEV_MODE=true tự động dùng SQLite/fakeredis/Qdrant in-memory)
        ↓
[4] Upload PDF
        ↓
[5] Test chat
```

### A.3 Model 1 — gemma2:2b (Local, Fast)

**Đặc điểm:** Nhẹ (~1.6GB RAM), nhanh, phù hợp câu hỏi đơn giản.

```bash
# Cấu hình .env.dev
cat > rag-chatbot/backend/.env.dev << 'EOF'
DEV_MODE=true
DEBUG=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=gemma2:2b
FORCE_LLM_BACKEND=ollama
SECRET_KEY=dev-secret-key
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
EOF

# Khởi động (từ thư mục backend/)
cd rag-chatbot/backend
rm -f dev.db
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Kiểm tra health + model
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, which model are you?", "mode": "general"}' \
  --no-buffer | grep '"model"'
# → "model": "gemma2:2b"
```

### A.4 Model 2 — llama3.1:8b (Local, Smart)

**Đặc điểm:** Mạnh hơn (~4.7GB RAM), chất lượng cao, phù hợp câu hỏi phức tạp.

```bash
cat > rag-chatbot/backend/.env.dev << 'EOF'
DEV_MODE=true
DEBUG=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=llama3.1:8b
FORCE_LLM_BACKEND=ollama
SECRET_KEY=dev-secret-key
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
EOF

# Dừng server cũ → khởi động lại
kill $(lsof -ti:8000) 2>/dev/null; true
cd rag-chatbot/backend && rm -f dev.db
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Lưu ý RAM:** llama3.1:8b cần ~4.7GB. Kiểm tra: `ollama ps` hoặc `free -h`

### A.5 Model 3 — Gemini 1.5 Flash (Cloud API)

**Đặc điểm:** Không tốn RAM local, chất lượng cao, cần internet + API key.

```bash
# Lấy API key tại: https://aistudio.google.com/app/apikey

cat > rag-chatbot/backend/.env.dev << 'EOF'
DEV_MODE=true
DEBUG=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=gemini-1.5-flash
GEMINI_API_KEY=AIzaSy...your-key-here...
GEMINI_MODEL=gemini-1.5-flash
FORCE_LLM_BACKEND=gemini
SECRET_KEY=dev-secret-key
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
EOF

# Kiểm tra API key
python3 -c "
import httpx
lines = open('rag-chatbot/backend/.env.dev').read().splitlines()
key = next(l.split('=',1)[1] for l in lines if l.startswith('GEMINI_API_KEY='))
r = httpx.get(f'https://generativelanguage.googleapis.com/v1beta/models?key={key}', timeout=10)
print('Status:', r.status_code)
if r.status_code == 200:
    flash = [m['name'] for m in r.json().get('models',[]) if 'flash' in m['name'].lower()]
    print('Flash models:', flash[:3])
else:
    print('Error:', r.text[:200])
"
```

```bash
kill $(lsof -ti:8000) 2>/dev/null; true
cd rag-chatbot/backend && rm -f dev.db
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Lưu ý:** Field `"model"` trong SSE event `done` phản chiếu `OLLAMA_CHAT_MODEL`, không phải tên Gemini.
> Kiểm tra Gemini thực sự được gọi qua log: `grep -i "gemini\|google" /tmp/backend.log`

---

## PHẦN B — Docker Mode (PostgreSQL + Redis + Qdrant)

> Phù hợp khi test production-like, cần persistent storage, Celery worker.

### B.1 Kiểm Tra Trạng Thái Docker Services

```bash
# Xem tất cả container đang chạy
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Kết quả mong đợi khi đầy đủ:
# rag_postgres   Up (healthy)   0.0.0.0:5432->5432/tcp
# rag_redis      Up (healthy)   0.0.0.0:6379->6379/tcp
# rag_qdrant     Up (healthy)   0.0.0.0:6333-6334->6333-6334/tcp
# rag_ollama     Up (healthy)   0.0.0.0:11434->11434/tcp
# rag_backend    Up (healthy)   0.0.0.0:8000->8000/tcp
# rag_celery     Up (healthy)
# rag_frontend   Up (healthy)   0.0.0.0:3000->3000/tcp
```

### B.2 Kiểm Tra Từng Service

#### PostgreSQL
```bash
# Health check
docker exec rag_postgres pg_isready -U raguser -d ragdb
# → localhost:5432 - accepting connections

# Kết nối và kiểm tra extension pgvector
docker exec -it rag_postgres psql -U raguser -d ragdb -c "SELECT extname, extversion FROM pg_extension;"
# Phải thấy: pgvector

# Kiểm tra tables
docker exec -it rag_postgres psql -U raguser -d ragdb -c "\dt"
```

#### Redis
```bash
# Ping
docker exec rag_redis redis-cli ping
# → PONG

# Xem thông tin
docker exec rag_redis redis-cli info server | grep redis_version
docker exec rag_redis redis-cli info memory | grep used_memory_human

# Kiểm tra keys đang có
docker exec rag_redis redis-cli keys "*" | head -20
```

#### Qdrant
```bash
# Health check
curl -s http://localhost:6333/healthz
# → {"title":"qdrant - vector search engine","version":"..."}

# Xem collections
curl -s http://localhost:6333/collections | python3 -m json.tool

# Chi tiết collection document_chunks
curl -s http://localhost:6333/collections/document_chunks | python3 -m json.tool
```

#### Ollama (trong Docker)
```bash
# Health check
curl -s http://localhost:11434/api/tags | python3 -c "
import json, sys
data = json.load(sys.stdin)
models = data.get('models', [])
print(f'Models loaded: {len(models)}')
for m in models:
    size_gb = m.get('size', 0) / 1e9
    print(f'  - {m[\"name\"]} ({size_gb:.1f} GB)')
"

# Xem model đang active (đang giữ trong VRAM/RAM)
docker exec rag_ollama ollama ps

# Pull model vào container (nếu chưa có)
docker exec rag_ollama ollama pull gemma2:2b
docker exec rag_ollama ollama pull llama3.1:8b
docker exec rag_ollama ollama pull nomic-embed-text
```

### B.3 Khởi Động Docker Stack

#### Khởi động lần đầu
```bash
cd /path/to/rag-chatbot

# Copy và điền secrets
cp .env.example .env
# Sửa .env: điền POSTGRES_PASSWORD, SECRET_KEY

# Build và khởi động tất cả services
docker compose up -d

# Theo dõi logs startup
docker compose logs -f --tail=50
```

#### Khởi động chỉ infrastructure (không build app)
```bash
# Chỉ khởi động PostgreSQL + Redis + Qdrant + Ollama
docker compose up -d postgres redis qdrant ollama

# Chờ services healthy
docker compose ps
```

#### Dừng và restart
```bash
# Dừng tất cả (giữ data volumes)
docker compose down

# Dừng + xóa volumes (reset hoàn toàn)
docker compose down -v

# Restart service cụ thể
docker compose restart backend
```

### B.4 Cấu Hình Backend Kết Nối Docker Services

Khi `DEV_MODE=false`, backend đọc từ `.env` (không phải `.env.dev`):

```bash
# .env — kết nối tới Docker containers
POSTGRES_HOST=localhost        # nếu chạy backend ngoài Docker
POSTGRES_PORT=5432
POSTGRES_USER=raguser
POSTGRES_PASSWORD=your_password
POSTGRES_DB=ragdb

REDIS_HOST=localhost
REDIS_PORT=6379

QDRANT_HOST=localhost
QDRANT_PORT=6333

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=gemma2:2b    # hoặc llama3.1:8b
FORCE_LLM_BACKEND=ollama        # hoặc gemini

SECRET_KEY=your-64-char-secret-key
```

> **Lưu ý host:** Khi backend chạy **trong Docker** (container `rag_backend`), dùng service names:
> `postgres`, `redis`, `qdrant`, `ollama` thay vì `localhost`.
> Khi backend chạy **ngoài Docker** (uvicorn trực tiếp), dùng `localhost`.

### B.5 Test LLM Models Với Docker Mode

#### Model 1 — gemma2:2b (Docker Ollama)
```bash
# Sửa .env (hoặc set env var)
export OLLAMA_CHAT_MODEL=gemma2:2b
export FORCE_LLM_BACKEND=ollama

# Nếu chạy backend trong Docker
docker compose up -d backend

# Kiểm tra
curl -s http://localhost:8000/health | python3 -m json.tool
```

#### Model 2 — llama3.1:8b (Docker Ollama)
```bash
# Đảm bảo model đã pull vào container
docker exec rag_ollama ollama pull llama3.1:8b

# Kiểm tra RAM: llama3.1:8b cần ~4.7GB
# docker-compose.yml cấp 6500m cho rag_ollama — đủ cho 1 model
docker stats rag_ollama --no-stream

# Sửa .env → OLLAMA_CHAT_MODEL=llama3.1:8b
# Restart backend
docker compose restart backend
```

#### Model 3 — Gemini 1.5 Flash (Cloud API, từ Docker)
```bash
# Thêm vào .env
GEMINI_API_KEY=AIzaSy...your-key-here...
GEMINI_MODEL=gemini-1.5-flash
FORCE_LLM_BACKEND=gemini

# Rebuild backend để load env mới
docker compose up -d --force-recreate backend
```

---

## PHẦN C — Upload Documents & Test Chat

### C.1 Upload PDF Files

```bash
# Dev Mode (từ thư mục rag-chatbot/)
for f in data/uploads/raw/*.pdf; do
  curl -s -X POST http://localhost:8000/api/v1/documents/upload \
    -F "file=@$f" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(f\"  {d['filename']}: {d['status']} ({d.get('chunk_count','?')} chunks)\")"
done

# Docker Mode — từ trong container backend
docker exec -it rag_backend bash -c "
  for f in /app/data/uploads/raw/*.pdf; do
    curl -s -X POST http://localhost:8000/api/v1/documents/upload \
      -F 'file=@'\$f | python3 -c \
      'import json,sys; d=json.load(sys.stdin); print(d[\"filename\"], d[\"status\"])'
  done
"
```

### C.2 Test Chat Endpoints

```bash
# Test strict mode (dùng RAG context)
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the system architecture?", "mode": "strict"}' \
  --no-buffer

# Test general mode (không cần context)
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, which model are you?", "mode": "general"}' \
  --no-buffer | grep '"model"'

# Parse SSE response đẹp
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the main modules?", "mode": "strict"}' \
  --no-buffer | python3 -c "
import sys, json
answer, sources = [], []
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:].strip())
            if d.get('content') and not d.get('done'):
                answer.append(d['content'])
            if d.get('sources'):
                sources = [s['filename'] for s in d['sources'][:3]]
        except: pass
print('Answer:', ''.join(answer)[:400])
print('Sources:', sources)
"
```

### C.3 Script Test Cả 3 Models (Interactive)

Lưu thành `scripts/test_models.sh`:

```bash
#!/bin/bash
# Test cùng 1 câu hỏi với cả 3 models (phải sửa .env và restart giữa các lần)
BASE="http://localhost:8000"
QUESTION="${1:-What modules does the traffic violation detection system have?}"

echo "============================================"
echo "Testing: $QUESTION"
echo "============================================"

test_model() {
  local desc="$1"
  echo ""
  echo "--- $desc ---"
  curl -s -X POST "$BASE/api/v1/chat" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"$QUESTION\", \"mode\": \"strict\"}" \
    --no-buffer 2>/dev/null \
    | python3 -c "
import sys, json
answer, sources, model = [], [], ''
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:].strip())
            if d.get('content') and not d.get('done'):
                answer.append(d['content'])
            if d.get('sources'):
                sources = [s['filename'] for s in d['sources'][:2]]
            if d.get('done') and d.get('model'):
                model = d['model']
        except: pass
print('Model field:', model)
print('Answer:', ''.join(answer)[:400])
print('Sources:', sources)
"
}

echo ""
echo "Đảm bảo backend đang chạy với model đúng trước khi nhấn Enter"
echo ""

read -p "Model 1: gemma2:2b — nhấn Enter để test..."
test_model "gemma2:2b"

echo ""
read -p "Chuyển sang llama3.1:8b: sửa .env → restart backend → nhấn Enter..."
test_model "llama3.1:8b"

echo ""
read -p "Chuyển sang Gemini: sửa .env (FORCE_LLM_BACKEND=gemini) → restart → nhấn Enter..."
test_model "Gemini 1.5 Flash"

echo ""
echo "Done!"
```

```bash
chmod +x scripts/test_models.sh
./scripts/test_models.sh
# Hoặc với câu hỏi tùy chỉnh:
./scripts/test_models.sh "What are the input/output specifications?"
```

---

## PHẦN D — So Sánh 3 Models

| | gemma2:2b | llama3.1:8b | Gemini 1.5 Flash |
|--|-----------|-------------|-----------------|
| **RAM cần** | ~1.6GB | ~4.7GB | 0 (cloud) |
| **Tốc độ** | Nhanh | Vừa | Nhanh (network latency) |
| **Chất lượng** | Tốt | Tốt hơn | Tốt nhất |
| **Offline** | ✓ | ✓ | ✗ |
| **Chi phí** | Miễn phí | Miễn phí | Free tier / Pay-per-use |
| **Dev Mode** | ✓ | ✓ | ✓ |
| **Docker Mode** | ✓ | ✓ | ✓ |
| **Config key** | `OLLAMA_CHAT_MODEL=gemma2:2b` | `OLLAMA_CHAT_MODEL=llama3.1:8b` | `FORCE_LLM_BACKEND=gemini` |

---

## PHẦN E — Troubleshooting

### E.1 Docker Services

#### PostgreSQL không start
```bash
# Xem logs
docker compose logs postgres | tail -30

# Lỗi thường gặp: password authentication failed
# → Kiểm tra POSTGRES_PASSWORD trong .env khớp với DATABASE_URL

# Reset postgres data (mất toàn bộ data)
docker compose down postgres
docker volume rm rag-chatbot_postgres_data
docker compose up -d postgres
```

#### Redis không start
```bash
docker compose logs redis | tail -20

# Kiểm tra config file
cat infra/docker/redis/redis.conf

# Test kết nối từ host
redis-cli -h localhost -p 6379 ping
```

#### Qdrant không start hoặc collection lỗi
```bash
docker compose logs qdrant | tail -20

# Xóa và tạo lại collection
curl -X DELETE http://localhost:6333/collections/document_chunks
# Backend sẽ tự tạo lại khi restart

# Kiểm tra disk space (Qdrant cần space cho storage)
df -h
docker system df
```

#### Ollama OOM (Out of Memory)
```bash
# Container bị kill do thiếu RAM
docker stats rag_ollama

# Giải pháp 1: Tăng mem_limit trong docker-compose.yml
# Giải pháp 2: Chỉ dùng 1 model nhỏ
docker exec rag_ollama ollama rm llama3.1:8b  # xóa model nặng

# Giải pháp 3: Dùng GGUF quantized (nhẹ hơn)
docker exec rag_ollama ollama pull gemma2:2b  # Q4 quantized
```

### E.2 Dev Mode

#### Lỗi `model requires more system memory`
```bash
# Kiểm tra RAM khả dụng
free -h
ollama ps

# Chạy CPU-only (không dùng VRAM)
OLLAMA_NUM_GPU=0 ollama serve

# Hoặc thêm vào .env.dev
echo "OLLAMA_TIMEOUT=300" >> backend/.env.dev
```

#### Lỗi Gemini: `GEMINI_API_KEY not set` hoặc 403
```bash
grep GEMINI backend/.env.dev

# Test key trực tiếp
KEY=$(grep GEMINI_API_KEY backend/.env.dev | cut -d= -f2)
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$KEY" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK, models:', len(d.get('models',[])))"
```

#### Backend trả `"model": "gemma2:2b"` dù đang dùng Gemini
→ Expected behavior: field `model` trong SSE luôn dùng `OLLAMA_CHAT_MODEL`.
Kiểm tra Gemini thực sự được gọi:
```bash
grep -i "gemini\|_stream_gemini\|google" /tmp/backend.log | tail -5
```

### E.3 Reset Hoàn Toàn

#### Dev Mode
```bash
kill $(lsof -ti:8000) 2>/dev/null; true
rm -f rag-chatbot/backend/dev.db
# Sửa .env.dev → restart uvicorn → upload lại PDFs
```

#### Docker Mode
```bash
# Dừng tất cả
docker compose down

# Xóa data (PostgreSQL, Redis, Qdrant, Ollama models)
docker compose down -v

# Xóa images (để build lại từ đầu)
docker compose down --rmi local

# Start fresh
docker compose up -d
```

---

## PHẦN F — Kiểm Tra Nhanh (Health Check All)

```bash
#!/bin/bash
# Chạy từ thư mục gốc rag-chatbot/
echo "=== Health Check ==="

# Ollama
ollama_status=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(f'OK ({len(d.get(\"models\",[]))} models)')" 2>/dev/null || echo "FAIL")
echo "Ollama:     $ollama_status"

# PostgreSQL (Docker)
pg_status=$(docker exec rag_postgres pg_isready -U raguser -d ragdb 2>/dev/null | \
  grep -q "accepting" && echo "OK" || echo "FAIL/not running")
echo "PostgreSQL: $pg_status"

# Redis (Docker)
redis_status=$(docker exec rag_redis redis-cli ping 2>/dev/null | \
  grep -q "PONG" && echo "OK" || echo "FAIL/not running")
echo "Redis:      $redis_status"

# Qdrant (Docker)
qdrant_status=$(curl -s http://localhost:6333/healthz 2>/dev/null | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'OK v{d.get(\"version\",\"?\")}')" 2>/dev/null || echo "FAIL")
echo "Qdrant:     $qdrant_status"

# Backend API
backend_status=$(curl -s http://localhost:8000/health 2>/dev/null | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "FAIL/not running")
echo "Backend:    $backend_status"
```
