export type Candle = {
  time: string;
  close_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type CandleResponse = {
  symbol: string;
  interval: string;
  source: "binance_spot";
  is_live: boolean;
  count: number;
  candles: Candle[];
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export async function fetchCandles(
  symbol = "BTCUSDT",
  interval = "1h",
  limit = 100,
): Promise<CandleResponse> {
  const query = new URLSearchParams({ interval, limit: String(limit) });
  const response = await fetch(
    `${API_BASE}/api/v1/markets/${encodeURIComponent(symbol)}/candles?${query.toString()}`,
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Market data request failed (${response.status}).`);
  }
  return response.json() as Promise<CandleResponse>;
}
