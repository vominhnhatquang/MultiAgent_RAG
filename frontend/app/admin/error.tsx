"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw } from "lucide-react";

interface AdminErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function AdminError({ error, reset }: AdminErrorProps) {
  useEffect(() => {
    console.error("[Admin Error]", error);
  }, [error]);

  const isNetworkError = 
    error.message.includes("fetch") || 
    error.message.includes("network") ||
    error.message.includes("Failed to fetch");

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <div className="w-10" />
            <h1 className="text-lg font-semibold">Admin Dashboard</h1>
          </div>
        </div>
      </header>

      {/* Error Content */}
      <main className="mx-auto max-w-6xl p-4">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-8">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="h-16 w-16 rounded-full bg-destructive/20 flex items-center justify-center">
              <AlertCircle className="h-8 w-8 text-destructive" />
            </div>

            <div>
              <h2 className="text-xl font-semibold mb-2">
                {isNetworkError ? "Connection Error" : "Dashboard Error"}
              </h2>
              <p className="text-muted-foreground max-w-md">
                {isNetworkError 
                  ? "Unable to connect to the admin dashboard. Please check your connection to the backend server."
                  : "Something went wrong while loading the admin dashboard. Please try again."}
              </p>
            </div>

            <Button onClick={reset} variant="default" className="gap-2">
              <RefreshCw className="h-4 w-4" />
              Try Again
            </Button>

            {process.env.NODE_ENV === "development" && (
              <div className="mt-4 bg-background rounded-lg p-3 text-left overflow-auto max-w-full">
                <p className="text-xs font-mono text-destructive">{error.message}</p>
                {error.digest && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Digest: {error.digest}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
