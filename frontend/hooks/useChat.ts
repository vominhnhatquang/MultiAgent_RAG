"use client";

import { useCallback, useState, useRef } from "react";
import { sendMessage } from "@/lib/api";
import { streamChat } from "@/lib/sse";
import type { Message, Source } from "@/types";

interface UseChatReturn {
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: Source[];
  error: string | null;
  abortController: AbortController | null;
  sendMessage: (content: string, sessionId: string | null, mode: "strict" | "general") => Promise<string | null>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  abortStream: () => void;
  clearError: () => void;
  clearMessages: () => void;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingSources, setStreamingSources] = useState<Source[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStreamingContent("");
    setStreamingSources([]);
    setError(null);
  }, []);

  const abortStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const handleSendMessage = useCallback(
    async (content: string, sessionId: string | null, mode: "strict" | "general"): Promise<string | null> => {
      if (!content.trim()) {
        setError("Message cannot be empty");
        return null;
      }

      setError(null);
      setIsStreaming(true);
      setStreamingContent("");
      setStreamingSources([]);

      // Add user message immediately
      const userMessage: Message = {
        id: `temp-${Date.now()}`,
        role: "user",
        content: content.trim(),
        created_at: new Date().toISOString(),
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      let newSessionId: string | null = sessionId;
      let assistantContent = "";
      let assistantSources: Source[] = [];
      let assistantModel = "";
      let messageId = "";

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController();

      try {
        await streamChat(
          content.trim(),
          sessionId,
          mode,
          {
            onSession: (data) => {
              newSessionId = data.sessionId;
            },
            onSources: (data) => {
              assistantSources = data.sources;
              setStreamingSources(data.sources);
            },
            onToken: (token) => {
              assistantContent += token;
              setStreamingContent(assistantContent);
            },
            onDone: (data) => {
              assistantModel = data.model;
              messageId = data.messageId;
            },
            onNoData: (data) => {
              assistantContent = data.message;
              setStreamingContent(assistantContent);
            },
            onError: (err) => {
              setError(err.message);
            },
          },
          abortControllerRef.current.signal
        );

        // Add assistant message
        const assistantMessage: Message = {
          id: messageId || `assistant-${Date.now()}`,
          role: "assistant",
          content: assistantContent,
          created_at: new Date().toISOString(),
          timestamp: new Date().toISOString(),
          sources: assistantSources.length > 0 ? assistantSources : undefined,
          model: assistantModel || undefined,
        };

        setMessages((prev) => [...prev, assistantMessage]);
        setStreamingContent("");
        setStreamingSources([]);

        return newSessionId;
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          // User aborted - add partial message
          if (assistantContent) {
            const assistantMessage: Message = {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: assistantContent + "\n\n_[Stopped by user]_",
              created_at: new Date().toISOString(),
              timestamp: new Date().toISOString(),
              sources: assistantSources.length > 0 ? assistantSources : undefined,
              model: assistantModel || undefined,
            };
            setMessages((prev) => [...prev, assistantMessage]);
          }
          return newSessionId;
        }
        
        const errorMessage = err instanceof Error ? err.message : "Failed to send message";
        setError(errorMessage);
        return null;
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    []
  );

  return {
    messages,
    isStreaming,
    streamingContent,
    streamingSources,
    error,
    abortController: abortControllerRef.current,
    sendMessage: handleSendMessage,
    setMessages,
    abortStream,
    clearError,
    clearMessages,
  };
}
