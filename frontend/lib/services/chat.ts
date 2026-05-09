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
  return r.json();
}
