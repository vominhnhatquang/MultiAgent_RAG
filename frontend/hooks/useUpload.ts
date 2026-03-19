"use client";

import { useCallback, useState } from "react";
import { uploadDocument, getDocuments, deleteDocument } from "@/lib/api";
import type { Document } from "@/types";

interface UploadProgress {
  fileName: string;
  progress: number;
  status: "pending" | "uploading" | "completed" | "error";
  error?: string;
  docId?: string;
}

interface UseUploadReturn {
  documents: Document[];
  uploadProgress: UploadProgress[];
  isLoading: boolean;
  error: string | null;
  fetchDocuments: () => Promise<void>;
  uploadFiles: (files: File[]) => Promise<void>;
  deleteDocumentById: (docId: string) => Promise<void>;
  clearError: () => void;
}

export function useUpload(): UseUploadReturn {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getDocuments(1, 50);
      setDocuments(response.documents);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch documents";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const uploadFiles = useCallback(async (files: File[]) => {
    setError(null);

    // Initialize progress for all files
    const initialProgress: UploadProgress[] = files.map((file) => ({
      fileName: file.name,
      progress: 0,
      status: "pending",
    }));
    setUploadProgress(initialProgress);

    // Upload files sequentially
    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      setUploadProgress((prev) =>
        prev.map((p, idx) =>
          idx === i ? { ...p, status: "uploading", progress: 10 } : p
        )
      );

      try {
        const result = await uploadDocument(file, (progress) => {
          setUploadProgress((prev) =>
            prev.map((p, idx) =>
              idx === i ? { ...p, progress } : p
            )
          );
        });

        setUploadProgress((prev) =>
          prev.map((p, idx) =>
            idx === i
              ? { ...p, status: "completed", progress: 100, docId: result.doc_id }
              : p
          )
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
        setUploadProgress((prev) =>
          prev.map((p, idx) =>
            idx === i ? { ...p, status: "error", error: message } : p
          )
        );
      }
    }

    // Refresh document list
    await fetchDocuments();
  }, [fetchDocuments]);

  const deleteDocumentById = useCallback(async (docId: string) => {
    setError(null);
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete document";
      setError(message);
    }
  }, []);

  return {
    documents,
    uploadProgress,
    isLoading,
    error,
    fetchDocuments,
    uploadFiles,
    deleteDocumentById,
    clearError,
  };
}
