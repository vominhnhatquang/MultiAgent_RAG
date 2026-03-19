"use client";

import { useCallback, useState } from "react";
import { sendMessage } from "@/lib/api";
import { readSSEStream } from "@/lib/sse";
import type { Message, Source } from "@/types";

interface UseChatReturn {
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;
  error: string | null;
  sendMessage: (content: string, sessionId: string | null) => Promise<string | null>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  clearError: () => void;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const handleSendMessage = useCallback(
    async (content: string, sessionId: string | null): Promise<string | null> => {
      if (!content.trim()) {
        setError("Message cannot be empty");
        return null;
      }

      setError(null);
      setIsStreaming(true);
      setStreamingContent("");

      // Add user message immediately
      const userMessage: Message = {
        id: `temp-${Date.now()}`,
        role: "user",
        content: content.trim(),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      let newSessionId: string | null = sessionId;
      let assistantContent = "";
      let assistantSources: Source[] = [];
      let assistantModel = "";

      try {
        const response = await sendMessage(content.trim(), sessionId, "strict");

        await readSSEStream(response, {
          onMeta: (data) => {
            newSessionId = data.sessionId;
          },
          onToken: (token) => {
            assistantContent += token;
            setStreamingContent(assistantContent);
          },
          onDone: (data) => {
            assistantSources = data.sources;
            assistantModel = data.model;
          },
          onNoData: (data) => {
            assistantContent = data.message;
            setStreamingContent(assistantContent);
          },
          onError: (err) => {
            setError(err.message);
          },
        });

        // Add assistant message
        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: assistantContent,
          created_at: new Date().toISOString(),
          sources: assistantSources,
          model_used: assistantModel,
        };

        setMessages((prev) => [...prev, assistantMessage]);
        setStreamingContent("");

        return newSessionId;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to send message";
        setError(errorMessage);
        return null;
      } finally {
        setIsStreaming(false);
      }
    },
    []
  );

  return {
    messages,
    isStreaming,
    streamingContent,
    error,
    sendMessage: handleSendMessage,
    setMessages,
    clearError,
  };
}
