#!/bin/bash
# Test cùng 1 câu hỏi với model hiện tại đang chạy
# Chạy sau khi backend đã up và PDFs đã được upload
# Usage: bash scripts/test_models.sh [câu hỏi tùy chọn]

BASE="http://localhost:8000"
QUESTION="${1:-What are the main components and modules of the system?}"

# Kiểm tra backend
if ! curl -sf "$BASE/health" > /dev/null 2>&1; then
  echo "ERROR: Backend chưa chạy tại $BASE"
  echo "  Chạy: cd backend && .venv/bin/uvicorn app.main:app --port 8000 --reload"
  exit 1
fi

# Kiểm tra có documents chưa
DOC_COUNT=$(curl -sf "$BASE/api/v1/documents" | python3 -c \
  "import json,sys; print(len(json.load(sys.stdin).get('documents', [])))" 2>/dev/null || echo 0)

if [ "$DOC_COUNT" -eq 0 ]; then
  echo "WARNING: Chưa có document nào. Upload PDFs trước:"
  echo "  for f in data/uploads/raw/*.pdf; do"
  echo "    curl -s -X POST $BASE/api/v1/documents/upload -F 'file=@\$f'"
  echo "  done"
  exit 1
fi

echo "================================================================"
echo "BACKEND: $BASE  |  DOCUMENTS: $DOC_COUNT"
echo "QUESTION: $QUESTION"
echo "================================================================"
echo ""

# Strict mode
echo "[STRICT MODE — chỉ trả lời từ tài liệu]"
echo "---"
curl -s -X POST "$BASE/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$QUESTION\", \"mode\": \"strict\"}" \
  --no-buffer 2>/dev/null \
  | python3 -c "
import sys, json
answer = []
sources = []
model = ''
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:].strip())
            if d.get('content') and not d.get('done'):
                answer.append(d['content'])
            if d.get('sources'):
                sources = [(s['filename'], s.get('score', 0)) for s in d['sources'][:3]]
            if d.get('model'):
                model = d['model']
            if d.get('message'):   # no_data
                answer = [d['message']]
        except:
            pass

print('ANSWER:')
print(''.join(answer)[:600])
print()
print('MODEL CONFIG:', model or 'unknown')
print('SOURCES:')
for fname, score in sources:
    print(f'  - {fname}  (score: {score:.4f})')
"

echo ""
echo "================================================================"
echo ""

# General mode
echo "[GENERAL MODE — có thể trả lời ngoài tài liệu]"
echo "---"
curl -s -X POST "$BASE/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$QUESTION\", \"mode\": \"general\"}" \
  --no-buffer 2>/dev/null \
  | python3 -c "
import sys, json
answer = []
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:].strip())
            if d.get('content') and not d.get('done'):
                answer.append(d['content'])
        except:
            pass
print(''.join(answer)[:400])
"
