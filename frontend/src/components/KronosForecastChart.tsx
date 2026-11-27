import { useEffect, useRef } from "react";
import { CandlestickSeries, createChart, type CandlestickData, type UTCTimestamp } from "lightweight-charts";
import type { ForecastCandle } from "../lib/marketData";

type Props = { historical: ForecastCandle[]; predicted: ForecastCandle[] };

export default function KronosForecastChart({ historical, predicted }: Props) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element || historical.length === 0 || predicted.length === 0) return;
    const chart = createChart(element, {
      width: element.clientWidth,
      height: 260,
      layout: { background: { color: "#0e141c" }, textColor: "#8290a2", fontFamily: "DM Mono, monospace", fontSize: 10 },
      grid: { vertLines: { color: "#1b2631" }, horzLines: { color: "#1b2631" } },
      rightPriceScale: { borderColor: "#293543" },
      timeScale: { borderColor: "#293543", timeVisible: true, rightOffset: 3, barSpacing: 7 },
      handleScroll: true,
      handleScale: true,
    });
    const toData = (items: ForecastCandle[]): CandlestickData<UTCTimestamp>[] => items.map((c) => ({
      time: Math.floor(Date.parse(c.time) / 1000) as UTCTimestamp,
      open: c.open, high: c.high, low: c.low, close: c.close,
    }));
    const historySeries = chart.addSeries(CandlestickSeries, {
      upColor: "#35c99a", downColor: "#e4777c", borderUpColor: "#35c99a", borderDownColor: "#e4777c",
      wickUpColor: "#35c99a", wickDownColor: "#e4777c", lastValueVisible: true,
    });
    historySeries.setData(toData(historical));
    const forecastSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#6c9ee8", downColor: "#d6a65a", borderUpColor: "#6c9ee8", borderDownColor: "#d6a65a",
      wickUpColor: "#6c9ee8", wickDownColor: "#d6a65a", lastValueVisible: true,
    });
    forecastSeries.setData(toData(predicted));
    chart.timeScale().fitContent();
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) chart.applyOptions({ width });
    });
    observer.observe(element);
    return () => { observer.disconnect(); chart.remove(); };
  }, [historical, predicted]);
  return <div ref={host} className="market-chart" aria-label="Historical and Kronos predicted candlestick series" />;
}
