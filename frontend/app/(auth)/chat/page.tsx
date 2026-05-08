"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { SendIcon, BotIcon, UserIcon, AlertCircleIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatMessage, sendChatMessage } from "@/lib/services/chat";
import { ChatCostBadge } from "@/components/llm/ChatCostBadge";

const OUT_OF_SCOPE_TYPE = "out_of_scope";

function isOutOfScope(content: string): boolean {
  try {
    const obj = JSON.parse(content);
    return obj?.type === OUT_OF_SCOPE_TYPE;
  } catch {
    return false;
  }
}

function MessageBubble({ message }: { message: ChatMessage & { error?: boolean } }) {
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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionCost, setSessionCost] = useState({ costUsd: 0, costThb: 0, messageCount: 0 });
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMessage: ChatMessage = { role: "user", content: text };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const result = await sendChatMessage(updatedMessages);
      setMessages((prev) => [...prev, { role: "assistant", content: result.content }]);
      setSessionCost((prev) => ({
        costUsd: prev.costUsd + result.cost_usd,
        costThb: prev.costThb + result.cost_thb,
        messageCount: prev.messageCount + 1,
      }));
    } catch (e) {
      setError((e as Error).message ?? "Something went wrong. Try again.");
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }, [input, loading, messages]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-3xl mx-auto">
      <PageHeader title="Chat" />

      <div className="flex-1 overflow-y-auto py-4 space-y-4 px-1">
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
          <MessageBubble key={i} message={msg} />
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

      <div className="border-t bg-background py-3">
        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 max-h-40 overflow-y-auto"
            placeholder="Ask about your portfolio..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <Button
            size="sm"
            disabled={!input.trim() || loading}
            onClick={handleSend}
            className="h-9 w-9 p-0 rounded-xl shrink-0"
          >
            <SendIcon className="size-4" />
          </Button>
        </div>
        <div className="flex items-center justify-between mt-1.5 px-1">
          <p className="text-[11px] text-muted-foreground">
            Finance topics only — portfolio, investments, markets. Press Enter to send.
          </p>
          <ChatCostBadge session={sessionCost} />
        </div>
      </div>
    </div>
  );
}
