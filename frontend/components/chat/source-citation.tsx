"use client";

import { cn } from "@/lib/utils";
import type { Source } from "@/types";
import { FileText } from "lucide-react";

interface SourceCitationProps {
  source: Source;
  index: number;
}

export function SourceCitation({ source, index }: SourceCitationProps) {
  const scorePercent = Math.round((source.score || 0) * 100);
  
  return (
    <div className="rounded-lg border bg-card p-3 text-sm">
      <div className="flex items-start gap-2">
        <FileText className="h-4 w-4 shrink-0 text-muted-foreground mt-0.5" />
        <div className="flex-1 min-w-0 space-y-1.5">
          {/* File name and page */}
          <div className="font-medium truncate">
            {source.doc_name || source.doc_id}
            {source.page > 0 && (
              <span className="text-muted-foreground ml-1">
                — Page {source.page}
              </span>
            )}
          </div>
          
          {/* Relevance score bar */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              Relevance:
            </span>
            <div className="h-2 flex-1 max-w-[100px] rounded-full bg-muted overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full",
                  scorePercent >= 80 ? "bg-green-500" :
                  scorePercent >= 60 ? "bg-yellow-500" : "bg-red-500"
                )}
                style={{ width: `${scorePercent}%` }}
              />
            </div>
            <span className="text-xs text-muted-foreground w-10">
              {scorePercent}%
            </span>
          </div>
          
          {/* Snippet */}
          {source.snippet && (
            <p className="text-xs text-muted-foreground line-clamp-2 italic">
              "{source.snippet.substring(0, 150)}..."
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
