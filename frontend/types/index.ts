// API Types for RAG Chatbot Frontend

export interface Session {
  id: string;
  title: string;
  mode: "strict" | "general";
  tier: "hot" | "warm" | "cold";
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  timestamp?: string;
  sources?: Source[];
  model_used?: string;
  model?: string;
  difficulty?: "easy" | "medium" | "hard";
  total_tokens?: number;
}

export interface Source {
  doc_id: string;
  doc_name?: string;
  filename?: string;
  page: number;
  chunk_id?: string;
  score: number;
  snippet?: string;
}

export interface SessionDetail extends Session {
  messages: Message[];
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: "processing" | "indexed" | "error";
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at?: string;
}

export interface UploadResponse {
  doc_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: "processing";
  created_at: string;
}

export interface Pagination {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface SessionsResponse {
  sessions: Session[];
  pagination: Pagination;
}

export interface DocumentsResponse {
  documents: Document[];
  pagination: Pagination;
}

// SSE Event Types
export interface SSEMetaEvent {
  event: "meta";
  data: {
    session_id: string;
    model: string;
    mode: "strict" | "general";
    difficulty?: "easy" | "medium" | "hard";
  };
}

export interface SSETokenEvent {
  event: "token";
  data: {
    content: string;
    done: boolean;
  };
}

export interface SSEDoneEvent {
  event: "done";
  data: {
    content: string;
    done: true;
    sources: Source[];
    model: string;
    difficulty?: "easy" | "medium" | "hard";
    total_tokens: number;
  };
}

export interface SSENoDataEvent {
  event: "no_data";
  data: {
    message: string;
    code: "NO_RELEVANT_DATA";
  };
}

export interface SSEErrorEvent {
  event: "error";
  data: {
    error: string;
    code: string;
  };
}

export type SSEEvent =
  | SSEMetaEvent
  | SSETokenEvent
  | SSEDoneEvent
  | SSENoDataEvent
  | SSEErrorEvent;

// API Error
export interface ApiError {
  error: string;
  message: string;
  code: string;
}

export interface FeedbackRequest {
  message_id: string;
  rating: "thumbs_up" | "thumbs_down";
  comment?: string;
}

// Admin Types
export interface SystemStats {
  documents: {
    total: number;
    indexed: number;
    processing: number;
    error: number;
  };
  chunks: {
    total: number;
  };
  sessions: {
    total: number;
    hot: number;
    warm: number;
    cold: number;
  };
  feedback: {
    thumbs_up: number;
    thumbs_down: number;
    satisfaction_rate: number;
  };
  models: {
    loaded: string[];
    available: string[];
  };
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  services?: {
    postgres: { status: string; latency_ms: number };
    qdrant: { status: string; latency_ms: number; vectors_count: number };
    redis: { status: string; used_memory_mb: number };
    ollama: { status: string; models_loaded: string[] };
  };
  memory?: {
    total_gb: number;
    used_gb: number;
    available_gb: number;
  };
}

export interface MemoryStats {
  total_gb: number;
  used_gb: number;
  services: {
    ollama: { used_mb: number; limit_mb: number };
    postgres: { used_mb: number; limit_mb: number };
    qdrant: { used_mb: number; limit_mb: number };
    redis: { used_mb: number; limit_mb: number };
    backend: { used_mb: number; limit_mb: number };
    frontend: { used_mb: number; limit_mb: number };
  };
}
