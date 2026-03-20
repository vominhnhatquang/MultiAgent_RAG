// API Client for RAG Chatbot
// Base URL: http://localhost:8000/api/v1

import type { 
  Document, 
  DocumentsResponse, 
  Session, 
  SessionDetail, 
  UploadResponse,
  SystemStats,
  HealthStatus,
  MemoryStats,
  FeedbackRequest
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { 
      "Content-Type": "application/json", 
      ...options?.headers 
    },
  });
  
  if (!res.ok) {
    const body = await res.json().catch(() => ({
      error: "unknown",
      message: res.statusText,
    }));
    throw new ApiError(res.status, body.error || "unknown", body.message || res.statusText);
  }
  
  return res.json();
}

// Documents API
export const api = {
  // Documents
  uploadDocument: async (file: File, onProgress?: (progress: number) => void): Promise<UploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    
    const res = await fetch(`${API_BASE_URL}/documents/upload`, { 
      method: "POST", 
      body: form 
    });
    
    if (onProgress) onProgress(100);
    
    if (!res.ok) {
      const body = await res.json().catch(() => ({
        error: "unknown",
        message: res.statusText,
      }));
      throw new ApiError(res.status, body.error || "unknown", body.message || res.statusText);
    }
    
    return res.json();
  },
  
  getDocument: (id: string) => request<Document>(`/documents/${id}`),
  listDocuments: (page = 1, perPage = 20) => 
    request<DocumentsResponse>(`/documents?page=${page}&per_page=${perPage}&sort=created_at&order=desc`),
  deleteDocument: (id: string) => 
    request<{ doc_id: string; status: string; chunks_removed: number }>(`/documents/${id}`, { method: "DELETE" }),

  // Sessions
  getSession: (id: string) => request<SessionDetail>(`/sessions/${id}`),
  listSessions: (page = 1, perPage = 50) => 
    request<{ sessions: Session[]; pagination: { page: number; per_page: number; total: number; total_pages: number } }>(
      `/sessions?page=${page}&per_page=${perPage}`
    ),
  deleteSession: (id: string) => 
    request<{ session_id: string; deleted: boolean; messages_removed: number }>(`/sessions/${id}`, { method: "DELETE" }),
  updateSession: (id: string, data: { title?: string; mode?: "strict" | "general" }) => 
    request<Session>(`/sessions/${id}`, { 
      method: "PATCH", 
      body: JSON.stringify(data) 
    }),

  // Feedback
  sendFeedback: (sessionId: string, messageId: string, rating: "thumbs_up" | "thumbs_down", comment?: string) =>
    request<{ id: string; message_id: string; rating: string; created_at: string }>(
      `/sessions/${sessionId}/messages/${messageId}/feedback`, 
      { method: "POST", body: JSON.stringify({ rating, comment }) }
    ),

  // Admin
  getStats: () => request<SystemStats>("/admin/stats"),
  getHealth: () => request<HealthStatus>("/health"),
  getDetailedHealth: () => request<HealthStatus>("/health/detailed"),
  getMemory: () => request<MemoryStats>("/admin/memory"),
};

// Chat API - returns Response for SSE streaming
export async function sendMessage(
  message: string,
  sessionId: string | null,
  mode: "strict" | "general" = "strict",
  signal?: AbortSignal
): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      mode,
    }),
    signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: "unknown",
      message: response.statusText,
    }));
    throw new ApiError(response.status, error.error || "unknown", error.message || response.statusText);
  }

  return response;
}

export { API_BASE_URL };
