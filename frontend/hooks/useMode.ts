"use client";

import { useState, useCallback } from "react";

type ChatMode = "strict" | "general";

interface UseModeReturn {
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  toggleMode: () => void;
  isStrict: boolean;
  isGeneral: boolean;
}

export function useMode(initialMode: ChatMode = "strict"): UseModeReturn {
  const [mode, setModeState] = useState<ChatMode>(initialMode);

  const setMode = useCallback((newMode: ChatMode) => {
    setModeState(newMode);
  }, []);

  const toggleMode = useCallback(() => {
    setModeState((prev) => (prev === "strict" ? "general" : "strict"));
  }, []);

  return {
    mode,
    setMode,
    toggleMode,
    isStrict: mode === "strict",
    isGeneral: mode === "general",
  };
}
