"use client";

import { useEffect } from "react";
import Link from "next/link";
import { DropZone } from "@/components/upload/drop-zone";
import { UploadProgress } from "@/components/upload/upload-progress";
import { useUpload } from "@/hooks/useUpload";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, FileText, Trash2, AlertCircle } from "lucide-react";
import { toast } from "sonner";

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

  // Show error toast
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  const handleDrop = async (files: File[]) => {
    const validTypes = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/markdown", "text/plain"];
    const maxSize = 50 * 1024 * 1024; // 50MB

    const validFiles = files.filter((file) => {
      if (!validTypes.includes(file.type) && !file.name.endsWith('.md') && !file.name.endsWith('.txt')) {
        toast.error(`${file.name}: Unsupported file type. Use PDF, DOCX, MD, or TXT.`);
        return false;
      }
      if (file.size > maxSize) {
        toast.error(`${file.name}: File too large. Max 50MB.`);
        return false;
      }
      return true;
    });

    if (validFiles.length > 0) {
      await uploadFiles(validFiles);
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocumentById(docId);
      toast.success("Document deleted");
    } catch {
      toast.error("Failed to delete document");
    }
  };

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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "indexed":
        return "✅";
      case "processing":
        return "⏳";
      case "error":
        return "❌";
      default:
        return "📄";
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
        {/* Drop Zone */}
        <div className="mb-8">
          <DropZone onFilesDrop={handleDrop} />
        </div>

        {/* Upload Progress */}
        {uploadProgress.length > 0 && (
          <div className="mb-8">
            <UploadProgress files={uploadProgress} />
          </div>
        )}

        {/* Documents List */}
        <div>
          <h2 className="mb-4 text-lg font-semibold">
            Uploaded Documents ({documents.length})
          </h2>
          
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
              <p className="text-sm text-muted-foreground mt-1">
                Upload PDF, DOCX, MD, or TXT files to get started.
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
                      <span className="text-2xl">{getStatusIcon(doc.status)}</span>
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
                        {doc.error_message && (
                          <p className="text-xs text-destructive mt-1">
                            Error: {doc.error_message}
                          </p>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(doc.id)}
                      className="shrink-0 text-muted-foreground hover:text-destructive"
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
