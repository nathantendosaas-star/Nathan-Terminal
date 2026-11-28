export type MarketSubscription = { symbol: string; provider: "binance" | "twelvedata" };
export type MarketSession = {
  id: string;
  status: "ACTIVE" | "STOPPED" | "EXPIRED";
  started_at: string;
  expires_at: string;
  ended_at: string | null;
  interval: string;
  subscriptions: MarketSubscription[];
  maximum_duration_hours: number;
};
type SessionResponse = { active: boolean; session: MarketSession | null; maximum_duration_hours: number };
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1/sessions${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Session request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}
export function fetchCurrentSession(): Promise<SessionResponse> {
  return request<SessionResponse>("/current");
}
export function startMarketSession(interval: string): Promise<SessionResponse> {
  return request<SessionResponse>("/start", {
    method: "POST",
    body: JSON.stringify({
      interval,
      symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NVDA", "AAPL", "GOOGL"],
    }),
  });
}
export function stopMarketSession(sessionId: string): Promise<SessionResponse> {
  return request<SessionResponse>(`/${encodeURIComponent(sessionId)}/stop`, { method: "POST" });
}
