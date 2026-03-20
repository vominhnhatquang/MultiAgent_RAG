"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw } from "lucide-react";

interface UploadErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function UploadError({ error, reset }: UploadErrorProps) {
  useEffect(() => {
    console.error("[Upload Error]", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header Skeleton */}
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-4 px-4">
          <div className="w-10" />
          <h1 className="text-lg font-semibold">Upload Documents</h1>
        </div>
      </header>

      {/* Error Content */}
      <main className="mx-auto max-w-5xl p-4">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-8 text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 rounded-full bg-destructive/20 flex items-center justify-center">
              <AlertCircle className="h-8 w-8 text-destructive" />
            </div>
          </div>

          <h2 className="text-xl font-semibold mb-2">Failed to Load Upload Page</h2>
          <p className="text-muted-foreground mb-4">
            We couldn&apos;t load the document upload interface. This might be due to a network issue or server error.
          </p>

          <Button onClick={reset} variant="default" className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Try Again
          </Button>

          {process.env.NODE_ENV === "development" && (
            <div className="mt-4 bg-background rounded-lg p-3 text-left overflow-auto">
              <p className="text-xs font-mono text-destructive">{error.message}</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
