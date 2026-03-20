"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { Message } from "@/types";
import { User, Bot, ChevronDown, ChevronUp, FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SourceCitation } from "./source-citation";
import { FeedbackButtons } from "./feedback-buttons";

interface MessageBubbleProps {
  message: Message;
  isLast?: boolean;
  sessionId?: string;
  onFeedback?: (sessionId: string, messageId: string, rating: "thumbs_up" | "thumbs_down") => void;
}

export function MessageBubble({ message, isLast = false, sessionId, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [showSources, setShowSources] = useState(false);

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
      <div className="flex-1 space-y-3 overflow-hidden min-w-0">
        <div className="font-semibold">
          {isUser ? "You" : "Assistant"}
        </div>
        
        {/* Message Content */}
        <div className="markdown-content prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Sources Citation */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSources(!showSources)}
              className="h-8 px-2 text-xs"
            >
              <FileText className="h-3.5 w-3.5 mr-1.5" />
              {message.sources.length} source{message.sources.length > 1 ? "s" : ""}
              {showSources ? (
                <ChevronUp className="h-3.5 w-3.5 ml-1" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5 ml-1" />
              )}
            </Button>
            
            {showSources && (
              <div className="mt-2 space-y-2">
                {message.sources.map((source, index) => (
                  <SourceCitation key={source.chunk_id || index} source={source} index={index} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Model info & Feedback */}
        {!isUser && (
          <div className="flex items-center justify-between pt-2">
            <div className="text-xs text-muted-foreground">
              {message.model && `Model: ${message.model}`}
            </div>
            {isLast && onFeedback && sessionId && message.id && !message.id.startsWith("temp-") && (
              <FeedbackButtons messageId={message.id} sessionId={sessionId} onFeedback={onFeedback} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
