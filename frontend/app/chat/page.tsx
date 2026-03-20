"use client";

import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/sidebar/sidebar";
import { ChatContainer } from "@/components/chat/chat-container";
import { useChat } from "@/hooks/useChat";
import { useSession } from "@/hooks/useSession";
import { useMode } from "@/hooks/useMode";
import { useFeedback } from "@/hooks/useFeedback";
import { toast } from "sonner";

export default function ChatPage() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  
  const {
    sessions,
    currentSession,
    isLoading: isSessionLoading,
    fetchSessions,
    fetchSession,
    deleteSessionById,
    createNewSession,
  } = useSession();

  const {
    mode,
    toggleMode,
  } = useMode();

  const {
    messages,
    isStreaming,
    streamingContent,
    streamingSources,
    error: chatError,
    sendMessage,
    setMessages,
    abortStream,
    clearError: clearChatError,
  } = useChat();

  const {
    submitFeedback,
  } = useFeedback();

  // Load session messages when switching sessions
  useEffect(() => {
    if (currentSessionId) {
      fetchSession(currentSessionId);
    } else {
      setMessages([]);
    }
  }, [currentSessionId, fetchSession, setMessages]);

  // Update messages when currentSession changes
  useEffect(() => {
    if (currentSession?.messages) {
      setMessages(currentSession.messages);
    }
  }, [currentSession, setMessages]);

  // Show mode change toast
  const handleToggleMode = useCallback(() => {
    toggleMode();
    toast.success(`Switched to ${mode === "strict" ? "General" : "Strict"} mode`);
  }, [toggleMode, mode]);

  const handleSendMessage = useCallback(
    async (content: string) => {
      clearChatError();
      const newSessionId = await sendMessage(content, currentSessionId, mode);
      if (newSessionId && !currentSessionId) {
        setCurrentSessionId(newSessionId);
        fetchSessions();
      }
    },
    [currentSessionId, mode, sendMessage, clearChatError, fetchSessions]
  );

  const handleNewSession = useCallback(() => {
    setCurrentSessionId(null);
    setMessages([]);
    clearChatError();
  }, [setMessages, clearChatError]);

  const handleSelectSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
  }, []);

  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      await deleteSessionById(sessionId);
      if (currentSessionId === sessionId) {
        handleNewSession();
      }
    },
    [currentSessionId, deleteSessionById, handleNewSession]
  );

  const handleFeedback = useCallback(
    async (sessionId: string, messageId: string, rating: "thumbs_up" | "thumbs_down") => {
      await submitFeedback(sessionId, messageId, rating);
      toast.success("Feedback submitted!");
    },
    [submitFeedback]
  );

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        mode={mode}
        isLoading={isSessionLoading}
        onNewSession={handleNewSession}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onToggleMode={handleToggleMode}
      />
      <main className="flex-1 md:pl-72">
        <ChatContainer
          messages={messages}
          streamingContent={streamingContent}
          streamingSources={streamingSources}
          isStreaming={isStreaming}
          onSendMessage={handleSendMessage}
          onStopStream={abortStream}
          sessionId={currentSessionId}
          onFeedback={handleFeedback}
          error={chatError}
          onRetry={clearChatError}
          mode={mode}
        />
      </main>
    </div>
  );
}
