"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";
import type { Message } from "@/types";

interface ChatContainerProps {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  onSendMessage: (message: string) => void;
  error?: string | null;
}

export function ChatContainer({
  messages,
  streamingContent,
  isStreaming,
  onSendMessage,
  error,
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive or streaming
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const showStreamingMessage = isStreaming && streamingContent;

  return (
    <div className="flex h-full flex-col">
      {/* Messages Area */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl">
          {messages.length === 0 && !isStreaming ? (
            <div className="flex h-[50vh] flex-col items-center justify-center text-center p-8">
              <h2 className="text-2xl font-bold mb-2">Welcome to RAG Chatbot</h2>
              <p className="text-muted-foreground max-w-md">
                Start a conversation by typing a message below. 
                The AI will answer based on your uploaded documents.
              </p>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              
              {/* Streaming message */}
              {showStreamingMessage && (
                <MessageBubble
                  message={{
                    id: "streaming",
                    role: "assistant",
                    content: streamingContent,
                    created_at: new Date().toISOString(),
                  }}
                  isStreaming={true}
                />
              )}
            </>
          )}
          
          {/* Error message */}
          {error && (
            <div className="mx-4 my-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              <strong>Error:</strong> {error}
            </div>
          )}
          
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <ChatInput
        onSend={onSendMessage}
        isLoading={isStreaming}
        disabled={!!error}
      />
    </div>
  );
}
