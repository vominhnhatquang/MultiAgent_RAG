"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./message-bubble";
import { StreamingText } from "./streaming-text";
import { ChatInput } from "./chat-input";
import type { Message, Source } from "@/types";
import { Bot, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatContainerProps {
  messages: Message[];
  streamingContent: string;
  streamingSources: Source[];
  isStreaming: boolean;
  onSendMessage: (message: string) => void;
  onStopStream?: () => void;
  sessionId?: string | null;
  onFeedback?: (sessionId: string, messageId: string, rating: "thumbs_up" | "thumbs_down") => void;
  error?: string | null;
  onRetry?: () => void;
  mode?: "strict" | "general";
}

export function ChatContainer({
  messages,
  streamingContent,
  streamingSources,
  isStreaming,
  onSendMessage,
  onStopStream,
  sessionId,
  onFeedback,
  error,
  onRetry,
  mode = "strict",
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // Auto-scroll to bottom when new messages arrive or streaming
  useEffect(() => {
    if (isAtBottom) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingContent, isAtBottom]);

  // Track scroll position
  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollHeight, scrollTop, clientHeight } = scrollRef.current;
      const atBottom = scrollHeight - scrollTop - clientHeight < 100;
      setIsAtBottom(atBottom);
    }
  };

  const showStreamingMessage = isStreaming && streamingContent;

  return (
    <div className="flex h-full flex-col">
      {/* Messages Area */}
      <ScrollArea 
        className="flex-1" 
        onScroll={handleScroll}
      >
        <div className="mx-auto max-w-3xl">
          {messages.length === 0 && !isStreaming ? (
            <div className="flex h-[50vh] flex-col items-center justify-center text-center p-8">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Bot className="h-6 w-6 text-primary" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Welcome to RAG Chatbot</h2>
              <p className="text-muted-foreground max-w-md mb-6">
                Start a conversation by typing a message below. 
                The AI will answer based on your uploaded documents.
              </p>
              <div className="flex flex-wrap justify-center gap-2 max-w-lg">
                {mode === "strict" ? (
                  <>
                    <span className="text-xs bg-muted px-3 py-1.5 rounded-full">Strict Mode: Only document-based answers</span>
                  </>
                ) : (
                  <>
                    <span className="text-xs bg-muted px-3 py-1.5 rounded-full">General Mode: AI can answer general questions</span>
                  </>
                )}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <MessageBubble 
                  key={message.id} 
                  message={message} 
                  isLast={index === messages.length - 1 && !isStreaming}
                  sessionId={sessionId || undefined}
                  onFeedback={onFeedback}
                />
              ))}
              
              {/* Streaming message */}
              {showStreamingMessage && (
                <div className="flex gap-3 px-4 py-6 bg-muted/50">
                  <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border shadow bg-primary text-primary-foreground border-primary">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="flex-1 space-y-2 overflow-hidden">
                    <div className="font-semibold">Assistant</div>
                    <StreamingText 
                      text={streamingContent} 
                      isStreaming={isStreaming}
                    />
                    
                    {/* Streaming sources preview */}
                    {streamingSources.length > 0 && (
                      <div className="text-xs text-muted-foreground mt-2">
                        Found {streamingSources.length} relevant source{streamingSources.length > 1 ? "s" : ""}...
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
          
          {/* Error message */}
          {error && (
            <div className="mx-4 my-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-destructive font-medium">Error</p>
                  <p className="text-sm text-destructive/80">{error}</p>
                  {onRetry && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={onRetry}
                    >
                      Retry
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}
          
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <ChatInput
        onSend={onSendMessage}
        onStop={onStopStream}
        isLoading={isStreaming}
        disabled={!!error && !onRetry}
        placeholder={mode === "strict" ? "Ask about your documents..." : "Ask anything..."}
      />
    </div>
  );
}
