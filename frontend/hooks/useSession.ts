"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteSession, getSession, getSessions } from "@/lib/api";
import type { Message, Session, SessionDetail } from "@/types";

interface UseSessionReturn {
  sessions: Session[];
  currentSession: SessionDetail | null;
  isLoading: boolean;
  error: string | null;
  fetchSessions: () => Promise<void>;
  fetchSession: (sessionId: string) => Promise<void>;
  deleteSessionById: (sessionId: string) => Promise<void>;
  createNewSession: () => void;
  clearError: () => void;
}

export function useSession(): UseSessionReturn {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<SessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const fetchSessions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getSessions(1, 50);
      setSessions(response.sessions);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch sessions";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchSession = useCallback(async (sessionId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const session = await getSession(sessionId);
      setCurrentSession(session);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch session";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteSessionById = useCallback(async (sessionId: string) => {
    setError(null);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSession?.id === sessionId) {
        setCurrentSession(null);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete session";
      setError(message);
    }
  }, [currentSession?.id]);

  const createNewSession = useCallback(() => {
    setCurrentSession(null);
  }, []);

  // Auto-fetch sessions on mount
  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  return {
    sessions,
    currentSession,
    isLoading,
    error,
    fetchSessions,
    fetchSession,
    deleteSessionById,
    createNewSession,
    clearError,
  };
}
