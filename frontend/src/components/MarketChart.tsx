import { useEffect, useRef } from "react";
import {
  CandlestickSeries, HistogramSeries, LineSeries, createChart,
  type IChartApi, type ISeriesApi, type CandlestickData, type HistogramData,
  type LineData, type UTCTimestamp,
} from "lightweight-charts";
import type { Candle, TechnicalAnalysis } from "../lib/marketData";

type Props = { candles: Candle[]; technical: TechnicalAnalysis | null };
type PriceLine = ReturnType<ISeriesApi<"Candlestick">["createPriceLine"]>;
type ChartSeries = {
  candles: ISeriesApi<"Candlestick">;
  ema20: ISeriesApi<"Line">;
  ema50: ISeriesApi<"Line">;
  volume: ISeriesApi<"Histogram">;
};

function ema(values: number[], period: number): number[] {
  const output: number[] = [];
  const multiplier = 2 / (period + 1);
  let previous: number | null = null;
  values.forEach((value, index) => {
    if (index + 1 < period) return;
    if (previous === null) previous = values.slice(0, period).reduce((sum, item) => sum + item, 0) / period;
    else previous = (value - previous) * multiplier + previous;
    output.push(previous);
  });
  return output;
}

export default function MarketChart({ candles, technical }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ChartSeries | null>(null);
  const priceLinesRef = useRef<PriceLine[]>([]);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const chart = createChart(element, {
      width: Math.max(element.clientWidth, 320), height: 310,
      layout: { background: { color: "#0e141c" }, textColor: "#8290a2", fontFamily: "DM Mono, monospace", fontSize: 10 },
      grid: { vertLines: { color: "#1b2631" }, horzLines: { color: "#1b2631" } },
      rightPriceScale: { borderColor: "#293543", scaleMargins: { top: 0.08, bottom: 0.28 } },
      timeScale: { borderColor: "#293543", timeVisible: true, secondsVisible: false, rightOffset: 5, barSpacing: 8 },
      crosshair: { vertLine: { color: "#657587", labelBackgroundColor: "#253342" }, horzLine: { color: "#657587", labelBackgroundColor: "#253342" } },
      handleScroll: true, handleScale: true,
    });
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#35c99a", downColor: "#e4777c", borderUpColor: "#35c99a", borderDownColor: "#e4777c",
      wickUpColor: "#35c99a", wickDownColor: "#e4777c", priceLineVisible: true, lastValueVisible: true,
    });
    const ema20Series = chart.addSeries(LineSeries, { color: "#68a9df", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    const ema50Series = chart.addSeries(LineSeries, { color: "#bd91e5", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "", lastValueVisible: false, priceLineVisible: false });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    chartRef.current = chart;
    seriesRef.current = { candles: candleSeries, ema20: ema20Series, ema50: ema50Series, volume: volumeSeries };
    const observer = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width;
      if (width) chart.applyOptions({ width });
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart || candles.length === 0) return;
    const candleData: CandlestickData<UTCTimestamp>[] = candles.map(c => ({
      time: Math.floor(Date.parse(c.time) / 1000) as UTCTimestamp,
      open: c.open, high: c.high, low: c.low, close: c.close,
    }));
    series.candles.setData(candleData);
    const closes = candles.map(c => c.close);
    const ema20 = ema(closes, 20);
    const ema50 = ema(closes, 50);
    series.ema20.setData(candleData.slice(19).map((candle, index): LineData<UTCTimestamp> => ({ time: candle.time, value: ema20[index] })));
    series.ema50.setData(candleData.slice(49).map((candle, index): LineData<UTCTimestamp> => ({ time: candle.time, value: ema50[index] })));
    const volumeData: HistogramData<UTCTimestamp>[] = candles.map(c => ({
      time: Math.floor(Date.parse(c.time) / 1000) as UTCTimestamp,
      value: c.volume, color: c.close >= c.open ? "rgba(53,201,154,0.42)" : "rgba(228,119,124,0.42)",
    }));
    series.volume.setData(volumeData);
    chart.timeScale().fitContent();
  }, [candles]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    priceLinesRef.current.forEach(line => series.candles.removePriceLine(line));
    priceLinesRef.current = [];
    if (technical?.support) priceLinesRef.current.push(series.candles.createPriceLine({ price: technical.support.price, color: "#4f9ed1", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "SUP" }));
    if (technical?.resistance) priceLinesRef.current.push(series.candles.createPriceLine({ price: technical.resistance.price, color: "#d6a65a", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "RES" }));
  }, [technical]);

  return <div className="market-chart" ref={host} aria-label="Interactive candlestick chart with live OHLCV and volume" />;
}
