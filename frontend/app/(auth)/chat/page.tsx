// frontend/app/(auth)/chat/page.tsx
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { SendIcon, BotIcon, UserIcon, AlertCircleIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ChatMessageWithMeta,
  sendChatMessage,
  listChatSessions,
  createChatSession,
  getChatMessages,
  ChatSessionSummary,
} from "@/lib/services/chat";
import { ChatCostBadge } from "@/components/llm/ChatCostBadge";
import { SessionStrip } from "@/components/chat/SessionStrip";

const OUT_OF_SCOPE_TYPE = "out_of_scope";

function isOutOfScope(content: string): boolean {
  try {
    const obj = JSON.parse(content);
    return obj?.type === OUT_OF_SCOPE_TYPE;
  } catch {
    return false;
  }
}

function MessageMetaRow({ msg }: { msg: ChatMessageWithMeta }) {
  if (msg.role !== "assistant" || msg.tokens_in == null) return null;
  if (isOutOfScope(msg.content)) return null;

  const formatTokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
  const formatCost = (usd?: number, thb?: number) => {
    if (usd == null) return "";
    const usdStr = usd < 0.001 ? "< $0.001" : `$${usd.toFixed(3)}`;
    const thbStr = thb && thb > 0 ? ` / ฿${thb.toFixed(2)}` : "";
    return `${usdStr}${thbStr}`;
  };

  return (
    <div className="ml-10 mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground/60">
      <span>
        ↑{formatTokens(msg.tokens_in!)} ↓{formatTokens(msg.tokens_out ?? 0)}
      </span>
      <span>·</span>
      <span>{formatCost(msg.cost_usd, msg.cost_thb)}</span>
      {msg.model && (
        <>
          <span>·</span>
          <span>{msg.model}</span>
        </>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessageWithMeta }) {
  const isUser = message.role === "user";
  const outOfScope = !isUser && isOutOfScope(message.content);
  const displayContent = outOfScope
    ? "That's outside my scope. I can only help with finance and investment questions — try asking about your portfolio, a stock, or market trends."
    : message.content;

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-full mt-0.5",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        )}
      >
        {isUser ? <UserIcon className="size-3.5" /> : <BotIcon className="size-3.5" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-sm"
            : outOfScope
              ? "bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 rounded-tl-sm"
              : "bg-muted text-foreground rounded-tl-sm",
        )}
      >
        {displayContent}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageWithMeta[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const sessionCost = {
    costUsd: messages.reduce((s, m) => s + (m.cost_usd ?? 0), 0),
    costThb: messages.reduce((s, m) => s + (m.cost_thb ?? 0), 0),
    messageCount: messages.filter((m) => m.role === "assistant").length,
    tokensIn: messages.reduce((s, m) => s + (m.tokens_in ?? 0), 0),
    tokensOut: messages.reduce((s, m) => s + (m.tokens_out ?? 0), 0),
  };

  const loadSession = useCallback(async (id: string) => {
    setActiveSessionId(id);
    setMessages([]);
    setError(null);
    const msgs = await getChatMessages(id);
    setMessages(msgs);
  }, []);

  useEffect(() => {
    listChatSessions().then((s) => {
      setSessions(s);
      if (s.length > 0) loadSession(s[0].id);
    });
  }, [loadSession]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function handleNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setError(null);
  }

  function handleSessionRenamed(id: string, title: string) {
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)));
  }

  function handleSessionDeleted(id: string) {
    setSessions((prev) => {
      const remaining = prev.filter((s) => s.id !== id);
      if (activeSessionId === id) {
        if (remaining.length > 0) {
          loadSession(remaining[0].id);
        } else {
          setActiveSessionId(null);
          setMessages([]);
          setError(null);
        }
      }
      return remaining;
    });
  }

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    let sessionId = activeSessionId;

    setLoading(true);
    setError(null);

    try {
      if (!sessionId) {
        const created = await createChatSession(text);
        sessionId = created.id;
        setActiveSessionId(sessionId);
        const newSession: ChatSessionSummary = {
          id: sessionId,
          title: text.slice(0, 60),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setSessions((prev) => [newSession, ...prev]);
      }

      const userMessage: ChatMessageWithMeta = { role: "user", content: text };
      const updatedMessages = [...messages, userMessage];
      setMessages(updatedMessages);
      setInput("");
      const result = await sendChatMessage(sessionId, updatedMessages);
      const assistantMessage: ChatMessageWithMeta = {
        role: "assistant",
        content: result.content,
        tokens_in: result.tokens_in,
        tokens_out: result.tokens_out,
        cost_usd: result.cost_usd,
        cost_thb: result.cost_thb,
        model: result.model,
        provider: result.provider,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId ? { ...s, updated_at: new Date().toISOString() } : s,
        ),
      );
    } catch (e) {
      setError((e as Error).message ?? "Something went wrong. Try again.");
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }, [input, loading, messages, activeSessionId]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      <PageHeader title="Chat" />

      <SessionStrip
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={loadSession}
        onNewChat={handleNewChat}
        onSessionRenamed={handleSessionRenamed}
        onSessionDeleted={handleSessionDeleted}
      />

      <div className="flex-1 min-h-0 overflow-y-auto py-4 space-y-1 px-1">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center text-muted-foreground pb-16">
            <BotIcon className="size-10 opacity-30" />
            <div>
              <p className="font-medium text-foreground">Finance Assistant</p>
              <p className="text-sm mt-1">
                Ask about your portfolio, holdings, market performance, or specific stocks.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 text-sm">
              {[
                "What's my portfolio worth?",
                "Which holdings have the best returns?",
                "How much cash do I have?",
                "What's on my watchlist?",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="rounded-xl border border-border px-3 py-2 text-left text-sm hover:bg-muted transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className="space-y-0.5">
            <MessageBubble message={msg} />
            <MessageMetaRow msg={msg} />
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted mt-0.5">
              <BotIcon className="size-3.5 text-muted-foreground" />
            </div>
            <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 rounded-xl px-4 py-2.5">
            <AlertCircleIcon className="size-4 shrink-0" />
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="pt-3 pb-4 shrink-0">
        <div className="rounded-2xl border border-input bg-background focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20 transition-shadow">
          <textarea
            ref={textareaRef}
            rows={1}
            className="w-full resize-none bg-transparent px-4 pt-3 pb-2 text-sm placeholder:text-muted-foreground outline-none max-h-40 overflow-y-auto"
            placeholder="Ask about your portfolio..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <div className="flex items-center justify-between px-3 pb-2">
            <p className="text-[11px] text-muted-foreground/60">
              Finance topics only · Enter to send
            </p>
            <div className="flex items-center gap-2">
              <ChatCostBadge session={sessionCost} />
              <Button
                size="sm"
                disabled={!input.trim() || loading}
                onClick={handleSend}
                className="h-7 w-7 p-0 rounded-lg shrink-0"
              >
                <SendIcon className="size-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
