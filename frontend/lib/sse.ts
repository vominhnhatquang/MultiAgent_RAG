// SSE Parser for RAG Chatbot
// Handles Server-Sent Events from the chat endpoint

import type { Source, SSEEvent } from "@/types";

export type SSERawEvent =
  | { type: "meta"; sessionId: string; model: string; mode: "strict" | "general" }
  | { type: "token"; content: string }
  | { type: "done"; sources: Source[]; model: string; totalTokens: number }
  | { type: "no_data"; message: string; code: string }
  | { type: "error"; message: string; code: string };

export interface SSEHandlers {
  onMeta?: (data: { sessionId: string; model: string; mode: "strict" | "general" }) => void;
  onToken?: (content: string) => void;
  onDone?: (data: { sources: Source[]; model: string; totalTokens: number }) => void;
  onNoData?: (data: { message: string; code: string }) => void;
  onError?: (error: { message: string; code: string }) => void;
}

/**
 * Parse SSE text into events
 * Format: "event: token\ndata: {...}\n\n"
 */
export function parseSSE(buffer: string): { events: SSERawEvent[]; remainder: string } {
  const events: SSERawEvent[] = [];
  const lines = buffer.split("\n\n");
  const remainder = lines.pop() || "";

  for (const chunk of lines) {
    const event = parseSSEChunk(chunk);
    if (event) {
      events.push(event);
    }
  }

  return { events, remainder };
}

function parseSSEChunk(chunk: string): SSERawEvent | null {
  const lines = chunk.trim().split("\n");
  let eventType = "";
  let dataStr = "";

  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      dataStr = line.slice(6).trim();
    }
  }

  if (!eventType || !dataStr) {
    return null;
  }

  try {
    const data = JSON.parse(dataStr);

    switch (eventType) {
      case "meta":
        return {
          type: "meta",
          sessionId: data.session_id,
          model: data.model,
          mode: data.mode,
        };

      case "token":
        return {
          type: "token",
          content: data.content,
        };

      case "done":
        return {
          type: "done",
          sources: data.sources || [],
          model: data.model,
          totalTokens: data.total_tokens,
        };

      case "no_data":
        return {
          type: "no_data",
          message: data.message,
          code: data.code,
        };

      case "error":
        return {
          type: "error",
          message: data.error,
          code: data.code,
        };

      default:
        return null;
    }
  } catch {
    return null;
  }
}

/**
 * Read SSE stream with handlers
 */
export async function readSSEStream(
  response: Response,
  handlers: SSEHandlers
): Promise<void> {
  if (!response.body) {
    throw new Error("No response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const { events, remainder } = parseSSE(buffer);
      buffer = remainder;

      for (const event of events) {
        handleSSEEvent(event, handlers);
      }
    }

    // Process any remaining data
    if (buffer.trim()) {
      const { events } = parseSSE(buffer + "\n\n");
      for (const event of events) {
        handleSSEEvent(event, handlers);
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function handleSSEEvent(event: SSERawEvent, handlers: SSEHandlers): void {
  switch (event.type) {
    case "meta":
      handlers.onMeta?.({
        sessionId: event.sessionId,
        model: event.model,
        mode: event.mode,
      });
      break;

    case "token":
      handlers.onToken?.(event.content);
      break;

    case "done":
      handlers.onDone?.({
        sources: event.sources,
        model: event.model,
        totalTokens: event.totalTokens,
      });
      break;

    case "no_data":
      handlers.onNoData?.({
        message: event.message,
        code: event.code,
      });
      break;

    case "error":
      handlers.onError?.({
        message: event.message,
        code: event.code,
      });
      break;
  }
}
