"use client";

import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ModeToggle } from "./mode-toggle";
import type { Session } from "@/types";
import {
  Plus,
  MessageSquare,
  Trash2,
  FileUp,
  Menu,
  X,
  Settings,
  Shield,
} from "lucide-react";
import Link from "next/link";

interface SidebarProps {
  sessions: Session[];
  currentSessionId: string | null;
  mode: "strict" | "general";
  isLoading: boolean;
  onNewSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onToggleMode: () => void;
}

// Group sessions by date
function groupSessionsByDate(sessions: Session[]) {
  const groups: { [key: string]: Session[] } = {
    "Today": [],
    "Yesterday": [],
    "Last 7 days": [],
    "Older": [],
  };

  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const lastWeek = new Date(today);
  lastWeek.setDate(lastWeek.getDate() - 7);

  sessions.forEach((session) => {
    const sessionDate = new Date(session.updated_at);
    
    if (isSameDay(sessionDate, today)) {
      groups["Today"].push(session);
    } else if (isSameDay(sessionDate, yesterday)) {
      groups["Yesterday"].push(session);
    } else if (sessionDate > lastWeek) {
      groups["Last 7 days"].push(session);
    } else {
      groups["Older"].push(session);
    }
  });

  return groups;
}

function isSameDay(d1: Date, d2: Date) {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}

export function Sidebar({
  sessions,
  currentSessionId,
  mode,
  isLoading,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  onToggleMode,
}: SidebarProps) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const groupedSessions = useMemo(() => groupSessionsByDate(sessions), [sessions]);

  const sessionGroups = Object.entries(groupedSessions).filter(
    ([, groupSessions]) => groupSessions.length > 0
  );

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
          "fixed inset-y-0 left-0 z-40 w-72 bg-muted/50 border-r transition-transform duration-300 ease-in-out md:translate-x-0 flex flex-col",
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b px-4">
          <Link href="/" className="font-semibold flex items-center gap-2">
            <Shield className="h-5 w-5" />
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

        {/* Mode Toggle */}
        <ModeToggle mode={mode} onToggle={onToggleMode} />

        {/* Navigation Links */}
        <div className="px-4 pb-2 space-y-1">
          <Link href="/upload" onClick={() => setIsMobileOpen(false)}>
            <Button variant="outline" className="w-full justify-start gap-2">
              <FileUp className="h-4 w-4" />
              Upload Documents
            </Button>
          </Link>
          <Link href="/admin" onClick={() => setIsMobileOpen(false)}>
            <Button variant="outline" className="w-full justify-start gap-2">
              <Settings className="h-4 w-4" />
              Admin Dashboard
            </Button>
          </Link>
        </div>

        {/* Sessions List */}
        <ScrollArea className="flex-1 px-2">
          <div className="space-y-4 py-2">
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
              sessionGroups.map(([groupName, groupSessions]) => (
                <div key={groupName}>
                  <h3 className="px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {groupName}
                  </h3>
                  <div className="space-y-0.5">
                    {groupSessions.map((session) => (
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
                    ))}
                  </div>
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
