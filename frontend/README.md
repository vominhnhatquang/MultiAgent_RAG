# RAG Chatbot Frontend

Frontend cho RAG Chatbot sử dụng Next.js 14 + TypeScript + Tailwind CSS.

## Yêu cầu hệ thống

- Node.js 18+ 
- npm hoặc yarn
- Backend API đang chạy trên `http://localhost:8000` (xem hướng dẫn backend)

## Cài đặt lần đầu

```bash
# 1. Di chuyển vào thư mục frontend
cd rag-chatbot/frontend

# 2. Cài đặt dependencies
npm install

# 3. (Tùy chọn) Tạo file .env.local cho cấu hình môi trường
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
```

## Chạy Development Server

```bash
# Chạy server dev (port 3000 mặc định)
npm run dev

# Truy cập: http://localhost:3000
```

Server dev sẽ:
- Chạy trên `http://localhost:3000`
- Tự động reload khi file thay đổi
- Proxy API calls từ `/api/v1/*` → `http://localhost:8000/api/v1/*`

## Build Production

```bash
# Build cho production
npm run build

# Chạy production build
npm start
```

## Cấu trúc thư mục

```
frontend/
├── app/              # Next.js App Router
│   ├── chat/         # Chat interface
│   ├── upload/       # Upload page
│   └── layout.tsx    # Root layout
├── components/       # React components
│   ├── ui/           # Base UI components
│   ├── chat/         # Chat components
│   ├── sidebar/      # Sidebar components
│   └── upload/       # Upload components
├── hooks/            # Custom React hooks
├── lib/              # Utilities & API client
├── types/            # TypeScript types
└── public/           # Static assets
```

## Environment Variables

| Variable | Mô tả | Default |
|----------|-------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000/api/v1` |

## Troubleshooting

### Lỗi "Failed to fetch" khi chat
- Kiểm tra backend đã chạy chưa: `curl http://localhost:8000/api/v1/health`
- Kiểm tra CORS đã được cấu hình đúng chưa

### Lỗi port 3000 đã được sử dụng
```bash
# Tìm và kill process đang dùng port 3000
lsof -ti:3000 | xargs kill -9

# Hoặc chạy trên port khác
npm run dev -- --port 3001
```

### SSE streaming không hoạt động
- Kiểm tra backend có hỗ trợ SSE không
- Kiểm tra network tab trong DevTools → Response headers phải có `Content-Type: text/event-stream`

## Scripts

```bash
npm run dev      # Development server
npm run build    # Build production
npm run start    # Start production server
npm run lint     # Run ESLint
```

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript 5.x (Strict Mode)
- **Styling**: Tailwind CSS + CSS Variables
- **Icons**: Lucide React
- **State**: React Hooks (useState, useReducer)
- **API**: Native fetch API
- **Streaming**: ReadableStream API (SSE)
