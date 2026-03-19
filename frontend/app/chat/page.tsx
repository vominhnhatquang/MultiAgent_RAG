"use client";

import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/sidebar/sidebar";
import { ChatContainer } from "@/components/chat/chat-container";
import { useChat } from "@/hooks/useChat";
import { useSession } from "@/hooks/useSession";
import type { Message } from "@/types";

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
    messages,
    isStreaming,
    streamingContent,
    error: chatError,
    sendMessage,
    setMessages,
    clearError: clearChatError,
  } = useChat();

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

  const handleSendMessage = useCallback(
    async (content: string) => {
      clearChatError();
      const newSessionId = await sendMessage(content, currentSessionId);
      if (newSessionId && !currentSessionId) {
        setCurrentSessionId(newSessionId);
        // Refresh sessions list to show new session
        fetchSessions();
      }
    },
    [currentSessionId, sendMessage, clearChatError, fetchSessions]
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

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        isLoading={isSessionLoading}
        onNewSession={handleNewSession}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
      />
      <main className="flex-1 md:pl-72">
        <ChatContainer
          messages={messages}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
          onSendMessage={handleSendMessage}
          error={chatError}
        />
      </main>
    </div>
  );
}
