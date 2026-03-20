"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Square } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  onStop,
  isLoading = false,
  disabled = false,
  placeholder = "Type your message...",
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus on mount and after sending
  useEffect(() => {
    if (!isLoading && !disabled) {
      textareaRef.current?.focus();
    }
  }, [isLoading, disabled]);

  const handleSend = () => {
    if (!message.trim() || isLoading || disabled) return;
    onSend(message.trim());
    setMessage("");
  };

  const handleStop = () => {
    onStop?.();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isLoading) {
        handleStop();
      } else {
        handleSend();
      }
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [message]);

  return (
    <div className="border-t bg-background p-4">
      <div className="mx-auto flex max-w-3xl gap-2">
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          rows={1}
          className={cn(
            "min-h-[56px] resize-none py-4 pr-12",
            disabled && "opacity-50"
          )}
        />
        {isLoading ? (
          <Button
            onClick={handleStop}
            variant="destructive"
            size="icon"
            className="h-14 w-14 shrink-0"
          >
            <Square className="h-5 w-5 fill-current" />
          </Button>
        ) : (
          <Button
            onClick={handleSend}
            disabled={!message.trim() || isLoading || disabled}
            size="icon"
            className="h-14 w-14 shrink-0"
          >
            <Send className="h-5 w-5" />
          </Button>
        )}
      </div>
      <div className="mx-auto max-w-3xl mt-2 text-center text-xs text-muted-foreground">
        {isLoading ? "Press Enter or click the stop button to stop" : "Press Enter to send, Shift+Enter for new line"}
      </div>
    </div>
  );
}
