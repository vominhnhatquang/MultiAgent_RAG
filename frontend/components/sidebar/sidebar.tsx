"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Session } from "@/types";
import {
  Plus,
  MessageSquare,
  Trash2,
  FileUp,
  Menu,
  X,
} from "lucide-react";
import Link from "next/link";

interface SidebarProps {
  sessions: Session[];
  currentSessionId: string | null;
  isLoading: boolean;
  onNewSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

export function Sidebar({
  sessions,
  currentSessionId,
  isLoading,
  onNewSession,
  onSelectSession,
  onDeleteSession,
}: SidebarProps) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile Toggle */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed left-4 top-4 z-50 md:hidden"
        onClick={() => setIsMobileOpen(!isMobileOpen)}
      >
        {isMobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-72 bg-muted/50 border-r transition-transform duration-300 ease-in-out md:translate-x-0",
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col">
          {/* Header */}
          <div className="flex h-14 items-center justify-between border-b px-4">
            <Link href="/" className="font-semibold">
              RAG Chatbot
            </Link>
          </div>

          {/* New Chat Button */}
          <div className="p-4">
            <Button
              onClick={() => {
                onNewSession();
                setIsMobileOpen(false);
              }}
              className="w-full justify-start gap-2"
            >
              <Plus className="h-4 w-4" />
              New Chat
            </Button>
          </div>

          {/* Upload Link */}
          <div className="px-4 pb-2">
            <Link href="/upload" onClick={() => setIsMobileOpen(false)}>
              <Button variant="outline" className="w-full justify-start gap-2">
                <FileUp className="h-4 w-4" />
                Upload Documents
              </Button>
            </Link>
          </div>

          {/* Sessions List */}
          <ScrollArea className="flex-1 px-2">
            <div className="space-y-1 py-2">
              {isLoading ? (
                // Skeleton loading
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="px-2 py-2">
                    <Skeleton className="h-10 w-full" />
                  </div>
                ))
              ) : sessions.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                  No conversations yet.
                  <br />
                  Start a new chat!
                </div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className={cn(
                      "group flex items-center gap-2 rounded-lg px-2 py-2 text-sm cursor-pointer hover:bg-accent",
                      currentSessionId === session.id && "bg-accent"
                    )}
                    onClick={() => {
                      onSelectSession(session.id);
                      setIsMobileOpen(false);
                    }}
                  >
                    <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="flex-1 truncate">
                      {session.title || "Untitled Chat"}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>

          {/* Footer */}
          <div className="border-t p-4">
            <div className="text-xs text-muted-foreground text-center">
              Powered by Ollama
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}
    </>
  );
}
