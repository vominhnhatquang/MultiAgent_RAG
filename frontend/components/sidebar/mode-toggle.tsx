"use client";

import { cn } from "@/lib/utils";
import { Lock, MessageCircle } from "lucide-react";

interface ModeToggleProps {
  mode: "strict" | "general";
  onToggle: () => void;
  disabled?: boolean;
}

export function ModeToggle({ mode, onToggle, disabled = false }: ModeToggleProps) {
  const isStrict = mode === "strict";

  return (
    <div className="p-3">
      <div
        className={cn(
          "flex rounded-lg border p-1 cursor-pointer transition-colors",
          disabled && "opacity-50 cursor-not-allowed",
          "hover:bg-accent"
        )}
        onClick={!disabled ? onToggle : undefined}
      >
        {/* Strict Option */}
        <div
          className={cn(
            "flex flex-1 items-center justify-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-all",
            isStrict
              ? "bg-red-500/10 text-red-600 border border-red-200 dark:border-red-800"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Lock className="h-3.5 w-3.5" />
          <span>Strict</span>
        </div>

        {/* General Option */}
        <div
          className={cn(
            "flex flex-1 items-center justify-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-all",
            !isStrict
              ? "bg-green-500/10 text-green-600 border border-green-200 dark:border-green-800"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <MessageCircle className="h-3.5 w-3.5" />
          <span>General</span>
        </div>
      </div>
      <p className="mt-2 text-xs text-muted-foreground text-center">
        {isStrict 
          ? "Only answers from your documents" 
          : "AI can answer general questions"}
      </p>
    </div>
  );
}
