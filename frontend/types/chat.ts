// types/chat.ts
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  model?: string;
  total_tokens?: number;
  timestamp: string;
}

export interface Source {
  doc_id: string;
  doc_name: string;
  page: number;
  chunk_id: string;
  score: number;
  snippet?: string;
}

export interface Session {
  id: string;
  title: string;
  mode: "strict" | "general";
  tier: "hot" | "warm" | "cold";
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends Session {
  messages: Message[];
}

// SSE Event Types
export interface SSESessionEvent {
  event: "session";
  data: {
    session_id: string;
    model: string;
    mode: "strict" | "general";
  };
}

export interface SSESourcesEvent {
  event: "sources";
  data: {
    sources: Source[];
  };
}

export interface SSETokenEvent {
  event: "token";
  data: {
    token: string;
  };
}

export interface SSEDoneEvent {
  event: "done";
  data: {
    message_id: string;
    model_used: string;
    total_tokens: number;
  };
}

export interface SSEErrorEvent {
  event: "error";
  data: {
    error: string;
    message: string;
    code?: string;
  };
}

export interface SSENoDataEvent {
  event: "no_data";
  data: {
    message: string;
    code: "NO_RELEVANT_DATA";
  };
}

export type SSEEvent =
  | SSESessionEvent
  | SSESourcesEvent
  | SSETokenEvent
  | SSEDoneEvent
  | SSEErrorEvent
  | SSENoDataEvent;

// API Types
export interface ChatRequest {
  message: string;
  session_id: string | null;
  mode: "strict" | "general";
}

export interface FeedbackRequest {
  message_id: string;
  rating: "thumbs_up" | "thumbs_down";
  comment?: string;
}
