"use client";

import { useEffect } from "react";
import Link from "next/link";
import { DropZone } from "@/components/upload/drop-zone";
import { UploadProgress } from "@/components/upload/upload-progress";
import { useUpload } from "@/hooks/useUpload";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, FileText, Trash2 } from "lucide-react";

export default function UploadPage() {
  const {
    documents,
    uploadProgress,
    isLoading,
    error,
    fetchDocuments,
    uploadFiles,
    deleteDocumentById,
    clearError,
  } = useUpload();

  // Fetch documents on mount
  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "indexed":
        return "text-green-500";
      case "processing":
        return "text-yellow-500";
      case "error":
        return "text-destructive";
      default:
        return "text-muted-foreground";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-4 px-4">
          <Link href="/chat">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <h1 className="text-lg font-semibold">Upload Documents</h1>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-5xl p-4">
        {/* Error Alert */}
        {error && (
          <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            <strong>Error:</strong> {error}
            <button
              onClick={clearError}
              className="ml-2 underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Drop Zone */}
        <div className="mb-8">
          <DropZone onFilesDrop={uploadFiles} />
        </div>

        {/* Upload Progress */}
        {uploadProgress.length > 0 && (
          <div className="mb-8">
            <UploadProgress files={uploadProgress} />
          </div>
        )}

        {/* Documents List */}
        <div>
          <h2 className="mb-4 text-lg font-semibold">Uploaded Documents</h2>
          
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <FileText className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
              <p className="text-muted-foreground">
                No documents uploaded yet.
              </p>
            </div>
          ) : (
            <ScrollArea className="h-[400px] rounded-lg border">
              <div className="divide-y">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="h-8 w-8 shrink-0 text-muted-foreground" />
                      <div className="min-w-0">
                        <p className="truncate font-medium">{doc.filename}</p>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span>{formatFileSize(doc.file_size_bytes)}</span>
                          <span>•</span>
                          <span>{doc.chunk_count} chunks</span>
                          <span>•</span>
                          <span className={getStatusColor(doc.status)}>
                            {doc.status}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {formatDate(doc.created_at)}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => deleteDocumentById(doc.id)}
                      className="shrink-0"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>
      </main>
    </div>
  );
}
