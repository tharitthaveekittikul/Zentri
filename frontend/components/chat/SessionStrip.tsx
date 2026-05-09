// frontend/components/chat/SessionStrip.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { PlusIcon, XIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { renameChatSession, deleteChatSession } from "@/lib/services/chat";
import type { ChatSessionSummary } from "@/lib/services/chat";

interface SessionStripProps {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onSessionRenamed: (id: string, title: string) => void;
  onSessionDeleted: (id: string) => void;
}

function SessionChip({
  session,
  isActive,
  onSelect,
  onRename,
  onDelete,
}: {
  session: ChatSessionSummary;
  isActive: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.title);
  const [hovered, setHovered] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  function handleDoubleClick() {
    setDraft(session.title);
    setEditing(true);
  }

  function handleSave() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== session.title) {
      onRename(trimmed);
    }
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") setEditing(false);
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className="h-7 max-w-[160px] rounded-full border border-ring bg-background px-3 text-xs outline-none"
      />
    );
  }

  return (
    <div
      className="relative shrink-0"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        onClick={onSelect}
        onDoubleClick={handleDoubleClick}
        title="Double-click to rename"
        className={cn(
          "h-7 rounded-full border pl-3 text-xs transition-colors truncate",
          hovered ? "pr-6" : "pr-3",
          isActive
            ? "border-primary bg-primary/10 text-primary font-medium"
            : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
        )}
        style={{ maxWidth: 160 }}
      >
        {session.title}
      </button>
      {hovered && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 flex size-4 items-center justify-center rounded-full text-muted-foreground hover:text-destructive transition-colors"
          title="Delete conversation"
        >
          <XIcon className="size-3" />
        </button>
      )}
    </div>
  );
}

export function SessionStrip({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onSessionRenamed,
  onSessionDeleted,
}: SessionStripProps) {
  async function handleRename(id: string, title: string) {
    await renameChatSession(id, title);
    onSessionRenamed(id, title);
  }

  async function handleDelete(id: string) {
    await deleteChatSession(id);
    onSessionDeleted(id);
  }

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-2 px-1 scrollbar-none border-b">
      <button
        onClick={onNewChat}
        className="flex h-7 shrink-0 items-center gap-1 rounded-full border border-border bg-muted/40 px-3 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
      >
        <PlusIcon className="size-3" />
        New
      </button>
      {sessions.map((s) => (
        <SessionChip
          key={s.id}
          session={s}
          isActive={s.id === activeSessionId}
          onSelect={() => onSelectSession(s.id)}
          onRename={(title) => handleRename(s.id, title)}
          onDelete={() => handleDelete(s.id)}
        />
      ))}
    </div>
  );
}
