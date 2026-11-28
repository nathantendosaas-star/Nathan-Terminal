import type { Candle } from "./marketData";

const BINANCE_INTERVALS = new Set(["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"]);

export function connectBinanceKlineStream(
  symbol: string,
  interval: string,
  onCandle: (candle: Candle, closed: boolean) => void,
  onStatus: (status: "connecting" | "connected" | "disconnected" | "error") => void,
): () => void {
  const normalized = symbol.toLowerCase().replace(/[^a-z0-9]/g, "");
  if (!/^[a-z0-9]{5,20}$/.test(normalized) || !BINANCE_INTERVALS.has(interval)) {
    onStatus("error");
    return () => undefined;
  }

  let socket: WebSocket | null = null;
  let stopped = false;
  let retryTimer: number | undefined;
  let retryDelay = 1000;

  const connect = () => {
    if (stopped) return;
    onStatus("connecting");
    socket = new WebSocket(`wss://stream.binance.com:9443/ws/${normalized}@kline_${interval}`);
    socket.onopen = () => { retryDelay = 1000; onStatus("connected"); };
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(String(event.data));
        const k = payload?.k;
        if (!k || typeof k.t !== "number") return;
        const candle: Candle = {
          time: new Date(k.t).toISOString(),
          close_time: new Date(k.T).toISOString(),
          open: Number(k.o),
          high: Number(k.h),
          low: Number(k.l),
          close: Number(k.c),
          volume: Number(k.v),
        };
        if ([candle.open,candle.high,candle.low,candle.close,candle.volume].every(Number.isFinite)) {
          onCandle(candle, Boolean(k.x));
        }
      } catch { /* Ignore malformed provider frames; reconnect is handled by socket lifecycle. */ }
    };
    socket.onerror = () => onStatus("error");
    socket.onclose = () => {
      if (stopped) return;
      onStatus("disconnected");
      retryTimer = window.setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 30000);
    };
  };

  connect();
  return () => {
    stopped = true;
    if (retryTimer !== undefined) window.clearTimeout(retryTimer);
    socket?.close();
  };
}
