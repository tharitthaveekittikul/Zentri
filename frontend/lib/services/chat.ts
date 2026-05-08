import { api } from "@/lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  content: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cost_thb: number;
  model: string;
  provider: string;
}

export async function sendChatMessage(messages: ChatMessage[]): Promise<ChatResponse> {
  const r = await api.post("/api/v1/chat", { messages });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? "Chat request failed");
  }
  return r.json();
}
