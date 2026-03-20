"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { SystemStats, HealthStatus, MemoryStats } from "@/types";

interface UseAdminReturn {
  stats: SystemStats | null;
  health: HealthStatus | null;
  memory: MemoryStats | null;
  isLoading: boolean;
  error: string | null;
  fetchStats: () => Promise<void>;
  fetchHealth: () => Promise<void>;
  fetchMemory: () => Promise<void>;
  refreshAll: () => Promise<void>;
}

export function useAdmin(): UseAdminReturn {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [memory, setMemory] = useState<MemoryStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const data = await api.getStats();
      setStats(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch stats";
      setError(message);
    }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.getDetailedHealth();
      setHealth(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch health";
      setError(message);
    }
  }, []);

  const fetchMemory = useCallback(async () => {
    try {
      const data = await api.getMemory();
      setMemory(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch memory";
      setError(message);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await Promise.all([fetchStats(), fetchHealth(), fetchMemory()]);
    } catch {
      // Error already set by individual fetch functions
    } finally {
      setIsLoading(false);
    }
  }, [fetchStats, fetchHealth, fetchMemory]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  return {
    stats,
    health,
    memory,
    isLoading,
    error,
    fetchStats,
    fetchHealth,
    fetchMemory,
    refreshAll,
  };
}
