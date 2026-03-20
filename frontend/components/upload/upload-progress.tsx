"use client";

import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, FileText } from "lucide-react";

interface UploadFile {
  fileName: string;
  progress: number;
  status: "pending" | "uploading" | "processing" | "completed" | "error";
  error?: string;
  docId?: string;
}

interface UploadProgressProps {
  files: UploadFile[];
}

export function UploadProgress({ files }: UploadProgressProps) {
  if (files.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="font-medium">Upload Progress</h3>
      <div className="space-y-2">
        {files.map((file, index) => (
          <div
            key={`${file.fileName}-${index}`}
            className="rounded-lg border bg-card p-3"
          >
            <div className="flex items-center gap-3">
              <FileText className="h-5 w-5 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium">{file.fileName}</p>
                <div className="mt-1 flex items-center gap-2">
                  {/* Progress Bar */}
                  <div className="h-2 flex-1 rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-300",
                        file.status === "error"
                          ? "bg-destructive"
                          : file.status === "completed"
                          ? "bg-green-500"
                          : "bg-primary"
                      )}
                      style={{ width: `${file.progress}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground w-12 text-right">
                    {file.progress}%
                  </span>
                </div>
              </div>
              {/* Status Icon */}
              {file.status === "completed" && (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              )}
              {file.status === "error" && (
                <XCircle className="h-5 w-5 text-destructive" />
              )}
            </div>
            {/* Error Message */}
            {file.error && (
              <p className="mt-2 text-xs text-destructive">{file.error}</p>
            )}
            {/* Doc ID (for completed uploads) */}
            {file.docId && (
              <p className="mt-1 text-xs text-muted-foreground">
                Document ID: {file.docId}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
