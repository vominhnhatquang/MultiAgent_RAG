"use client";

import { useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import { Upload } from "lucide-react";

interface DropZoneProps {
  onFilesDrop: (files: File[]) => void;
  accept?: string;
  maxSize?: number; // in bytes
}

export function DropZone({
  onFilesDrop,
  accept = ".pdf,.docx,.md,.txt",
  maxSize = 50 * 1024 * 1024, // 50MB
}: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      const validFiles = files.filter((file) => {
        if (file.size > maxSize) {
          alert(`File ${file.name} is too large. Max size is ${maxSize / 1024 / 1024}MB`);
          return false;
        }
        return true;
      });

      if (validFiles.length > 0) {
        onFilesDrop(validFiles);
      }
    },
    [onFilesDrop, maxSize]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files ? Array.from(e.target.files) : [];
      const validFiles = files.filter((file) => {
        if (file.size > maxSize) {
          alert(`File ${file.name} is too large. Max size is ${maxSize / 1024 / 1024}MB`);
          return false;
        }
        return true;
      });

      if (validFiles.length > 0) {
        onFilesDrop(validFiles);
      }
      // Reset input
      e.target.value = "";
    },
    [onFilesDrop, maxSize]
  );

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors",
        isDragOver
          ? "border-primary bg-primary/5"
          : "border-muted-foreground/25 hover:border-muted-foreground/50"
      )}
    >
      <input
        type="file"
        multiple
        accept={accept}
        onChange={handleFileInput}
        className="absolute inset-0 cursor-pointer opacity-0"
      />
      <Upload
        className={cn(
          "mb-4 h-12 w-12 transition-colors",
          isDragOver ? "text-primary" : "text-muted-foreground"
        )}
      />
      <p className="mb-2 text-lg font-medium">
        {isDragOver ? "Drop files here" : "Drag & drop files here"}
      </p>
      <p className="text-sm text-muted-foreground">
        or click to browse (PDF, DOCX, MD, TXT up to 50MB)
      </p>
    </div>
  );
}
