// API Client for RAG Chatbot
// Base URL: http://localhost:8000/api/v1

import type { ApiError, Document, DocumentsResponse, Message, Session, SessionDetail, SessionsResponse, UploadResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClientError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: "Unknown error",
      message: "An unexpected error occurred",
      code: "UNKNOWN_ERROR",
    }));
    throw new ApiClientError(error.message, error.code, response.status);
  }
  return response.json() as Promise<T>;
}

// Sessions API
export async function getSessions(page = 1, perPage = 20): Promise<SessionsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/sessions?page=${page}&per_page=${perPage}`,
    { method: "GET", headers: { "Content-Type": "application/json" } }
  );
  return handleResponse<SessionsResponse>(response);
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${sessionId}`,
    { method: "GET", headers: { "Content-Type": "application/json" } }
  );
  return handleResponse<SessionDetail>(response);
}

export async function deleteSession(sessionId: string): Promise<{ session_id: string; deleted: boolean; messages_removed: number }> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${sessionId}`,
    { method: "DELETE", headers: { "Content-Type": "application/json" } }
  );
  return handleResponse(response);
}

export async function updateSession(
  sessionId: string,
  data: { title?: string; mode?: "strict" | "general" }
): Promise<Session> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${sessionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
  return handleResponse<Session>(response);
}

// Documents API
export async function getDocuments(page = 1, perPage = 20): Promise<DocumentsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/documents?page=${page}&per_page=${perPage}&sort=created_at&order=desc`,
    { method: "GET", headers: { "Content-Type": "application/json" } }
  );
  return handleResponse<DocumentsResponse>(response);
}

export async function getDocument(docId: string): Promise<Document> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${docId}`,
    { method: "GET", headers: { "Content-Type": "application/json" } }
  );
  return handleResponse<Document>(response);
}

export async function deleteDocument(docId: string): Promise<{ doc_id: string; status: string; chunks_removed: number }> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${docId}`,
    { method: "DELETE", headers: { "Content-Type": "application/json" } }
  );
  return handleResponse(response);
}

export async function uploadDocument(file: File, onProgress?: (progress: number) => void): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // Note: fetch doesn't support upload progress natively
  // For progress tracking, we'd need XMLHttpRequest, but we'll use fetch for simplicity
  // and update progress based on response received
  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (onProgress) {
    onProgress(100);
  }

  return handleResponse<UploadResponse>(response);
}

// Chat API (returns Response for SSE streaming)
export async function sendMessage(
  message: string,
  sessionId: string | null,
  mode: "strict" | "general" = "strict"
): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      mode,
    }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: "Unknown error",
      message: "An unexpected error occurred",
      code: "UNKNOWN_ERROR",
    }));
    throw new ApiClientError(error.message, error.code, response.status);
  }

  return response;
}

// Health check
export async function healthCheck(): Promise<{ status: string; timestamp: string }> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  return handleResponse(response);
}

export { ApiClientError };
