// frontend/lib/services/chat.ts
import { api } from "@/lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatMessageWithMeta extends ChatMessage {
  id?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  cost_thb?: number;
  model?: string;
  provider?: string;
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

export interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const r = await api.get("/api/v1/chat/sessions");
  if (!r.ok) return [];
  return r.json();
}

export async function createChatSession(title: string): Promise<{ id: string }> {
  const r = await api.post("/api/v1/chat/sessions", { title: title.slice(0, 60) });
  return r.json();
}

export async function renameChatSession(id: string, title: string): Promise<void> {
  await api.patch(`/api/v1/chat/sessions/${id}`, { title });
}

export async function deleteChatSession(id: string): Promise<void> {
  await api.delete(`/api/v1/chat/sessions/${id}`);
}

export async function getChatMessages(sessionId: string): Promise<ChatMessageWithMeta[]> {
  const r = await api.get(`/api/v1/chat/sessions/${sessionId}/messages`);
  if (!r.ok) return [];
  return r.json();
}

export async function sendChatMessage(
  sessionId: string,
  messages: ChatMessage[],
): Promise<ChatResponse> {
  const r = await api.post("/api/v1/chat", { messages, session_id: sessionId });
  return r.json();
}
