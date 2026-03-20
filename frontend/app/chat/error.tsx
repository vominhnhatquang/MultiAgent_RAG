"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw } from "lucide-react";

interface ChatErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ChatError({ error, reset }: ChatErrorProps) {
  useEffect(() => {
    console.error("[Chat Error]", error);
  }, [error]);

  const isNetworkError = 
    error.message.includes("fetch") || 
    error.message.includes("network") ||
    error.message.includes("Failed to fetch");

  return (
    <div className="flex-1 flex items-center justify-center bg-background p-4 md:pl-72">
      <div className="max-w-md w-full text-center space-y-4">
        {/* Error Icon */}
        <div className="flex justify-center">
          <div className="h-16 w-16 rounded-full bg-destructive/10 flex items-center justify-center">
            <AlertCircle className="h-8 w-8 text-destructive" />
          </div>
        </div>

        {/* Error Message */}
        <div className="space-y-2">
          <h2 className="text-xl font-semibold">
            {isNetworkError ? "Connection Error" : "Chat Error"}
          </h2>
          <p className="text-muted-foreground text-sm">
            {isNetworkError 
              ? "Unable to connect to the chat service. Please check your connection and try again."
              : "Something went wrong while loading the chat. Please try again."}
          </p>
        </div>

        {/* Action Button */}
        <Button onClick={reset} variant="default" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Try Again
        </Button>

        {/* Error Details (dev only) */}
        {process.env.NODE_ENV === "development" && (
          <div className="bg-muted rounded-lg p-3 text-left overflow-auto">
            <p className="text-xs font-mono text-destructive">{error.message}</p>
          </div>
        )}
      </div>
    </div>
  );
}
