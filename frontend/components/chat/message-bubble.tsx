"use client";

import { cn } from "@/lib/utils";
import type { Message } from "@/types";
import { User, Bot } from "lucide-react";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3 px-4 py-6",
        isUser ? "bg-background" : "bg-muted/50"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border shadow",
          isUser
            ? "bg-background border-border"
            : "bg-primary text-primary-foreground border-primary"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className="flex-1 space-y-2 overflow-hidden">
        <div className="font-semibold">
          {isUser ? "You" : "Assistant"}
        </div>
        <div className="markdown-content text-sm leading-relaxed">
          {message.content}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse" />
          )}
        </div>

        {/* Model info (for assistant messages) */}
        {!isUser && message.model_used && (
          <div className="text-xs text-muted-foreground">
            Model: {message.model_used}
          </div>
        )}
      </div>
    </div>
  );
}
