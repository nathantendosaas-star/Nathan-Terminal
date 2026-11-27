export type Candle = {
  time: string;
  close_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type TechnicalAnalysis = {
  method: "deterministic_ohlcv";
  candle_count: number;
  latest_close: number;
  rsi_14: number | null;
  macd: { line: number | null; signal: number | null; histogram: number | null };
  moving_averages: { ema_20: number | null; ema_50: number | null; sma_20: number | null; sma_50: number | null };
  atr_14: number | null;
  support: { price: number; distance_from_close_pct: number } | null;
  resistance: { price: number; distance_from_close_pct: number } | null;
  market_structure: string;
  notes: string[];
};

export type CandleResponse = {
  symbol: string;
  interval: string;
  source: "binance_spot" | "twelve_data";
  is_live: boolean;
  count: number;
  candles: Candle[];
  technical_analysis: TechnicalAnalysis;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export async function fetchCandles(
  symbol = "BTCUSDT",
  interval = "1h",
  limit = 100,
  provider: "binance" | "twelvedata" = "binance",
): Promise<CandleResponse> {
  const query = new URLSearchParams({ interval, limit: String(limit), provider });
  const response = await fetch(
    `${API_BASE}/api/v1/markets/${encodeURIComponent(symbol)}/candles?${query.toString()}`,
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Market data request failed (${response.status}).`);
  }
  return response.json() as Promise<CandleResponse>;
}
