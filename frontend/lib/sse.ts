// SSE Client for RAG Chatbot
// Uses fetch + ReadableStream because EventSource only supports GET

import type { Source, SSEEvent } from "@/types";

export interface SSECallbacks {
  onSession?: (data: { sessionId: string; model: string; mode: "strict" | "general"; difficulty?: string }) => void;
  onSources?: (data: { sources: Source[] }) => void;
  onToken?: (token: string) => void;
  onDone?: (data: { messageId: string; model: string; difficulty?: string; totalTokens: number }) => void;
  onNoData?: (data: { message: string; code: string }) => void;
  onError?: (error: { message: string; code: string }) => void;
}

/**
 * Parse SSE chunk into events
 * Format: "event: xxx\ndata: {...}\n\n"
 */
function parseSSEChunk(chunk: string): Array<{ event: string; data: unknown }> {
  const events: Array<{ event: string; data: unknown }> = [];
  const parts = chunk.split("\n\n");

  for (const part of parts) {
    if (!part.trim()) continue;

    const lines = part.split("\n");
    let eventType = "";
    let dataStr = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) eventType = line.slice(7).trim();
      else if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
    }

    if (!eventType || !dataStr) continue;

    try {
      const data = JSON.parse(dataStr);
      events.push({ event: eventType, data });
    } catch {
      console.warn("Failed to parse SSE data:", dataStr);
    }
  }

  return events;
}

/**
 * Read SSE stream with callbacks
 */
export async function streamChat(
  message: string,
  sessionId: string | null,
  mode: "strict" | "general",
  callbacks: SSECallbacks,
  signal?: AbortSignal
): Promise<void> {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, mode }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        if (!part.trim()) continue;

        const lines = part.split("\n");
        let eventType = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) eventType = line.slice(7).trim();
          else if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
        }

        if (!eventType || !dataStr) continue;

        try {
          const data = JSON.parse(dataStr);

          switch (eventType) {
            case "session":
              callbacks.onSession?.({
                sessionId: data.session_id,
                model: data.model,
                mode: data.mode,
                difficulty: data.difficulty,
              });
              break;
            case "sources":
              callbacks.onSources?.({ sources: data.sources });
              break;
            case "token":
              callbacks.onToken?.(data.content || data.token);
              break;
            case "done":
              callbacks.onDone?.({
                messageId: data.message_id,
                model: data.model || data.model_used,
                difficulty: data.difficulty,
                totalTokens: data.total_tokens,
              });
              break;
            case "no_data":
              callbacks.onNoData?.({
                message: data.message,
                code: data.code,
              });
              break;
            case "error":
              callbacks.onError?.({
                message: data.error || data.message,
                code: data.code || "error",
              });
              break;
          }
        } catch {
          console.warn("Failed to parse SSE data:", dataStr);
        }
      }
    }

    // Process remaining buffer
    if (buffer.trim()) {
      const lines = buffer.split("\n");
      let eventType = "";
      let dataStr = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
      }

      if (eventType && dataStr) {
        try {
          const data = JSON.parse(dataStr);
          if (eventType === "done") {
            callbacks.onDone?.({
              messageId: data.message_id,
              model: data.model || data.model_used,
              difficulty: data.difficulty,
              totalTokens: data.total_tokens,
            });
          }
        } catch {
          // ignore
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
