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
  sources?: Source[];
  model_used?: string;
}

export interface Source {
  doc_id: string;
  filename: string;
  page: number;
  score: number;
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
  created_at: string;
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
