// types/document.ts

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: "processing" | "indexed" | "error";
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadResponse {
  doc_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: "processing";
  created_at: string;
}

export interface DocumentsResponse {
  documents: Document[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export type UploadFileState = {
  fileName: string;
  progress: number;
  status: "pending" | "uploading" | "processing" | "completed" | "error";
  error?: string;
  docId?: string;
};
