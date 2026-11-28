import { useEffect, useState } from "react";

type Props = { symbol: string; price: number | null; timestamp: string | null; source: string };
type Status = { mode: string; open_trades: number; events: number; failed_deliveries: number; telegram_configured: boolean; automatic_execution: boolean };
type Event = { id: number; trade_id: number; symbol: string; event_type: string; observed_price: number; delivery_status: string; created_at: string; last_error?: string | null };

export default function MonitoringPanel({ symbol, price, timestamp, source }: Props) {
  const [status, setStatus] = useState<Status | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = async () => {
    const [s, e] = await Promise.all([fetch("/api/v1/monitoring/status"), fetch("/api/v1/monitoring/events")]);
    if (!s.ok || !e.ok) throw new Error("Monitoring service unavailable.");
    setStatus(await s.json());
    setEvents(await e.json());
  };
  useEffect(() => { refresh().catch(error => setMessage(error.message)); }, []);
  const evaluate = async () => {
    if (price === null || !timestamp) return;
    setBusy(true); setMessage("");
    try {
      const response = await fetch("/api/v1/monitoring/evaluate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, current_price: price, market_data_timestamp: timestamp, source }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Snapshot evaluation failed.");
      setMessage(body.new_events.length ? `${body.new_events.length} new alert event(s) recorded.` : "Snapshot checked. No new stop-loss or take-profit event.");
      await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Monitoring request failed."); }
    finally { setBusy(false); }
  };
  const retry = async (id: number) => {
    try {
      const response = await fetch(`/api/v1/monitoring/events/${id}/retry`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Retry failed.");
      setMessage(`Alert #${id}: ${body.delivery_status}.`); await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Retry failed."); }
  };
  return <div className="monitoring-workspace">
    <div className="notice"><b>Snapshot-driven monitoring</b> — evaluates the latest fetched candle only when you request a check. It does not run a background price watcher, close trades, or place orders.</div>
    <div className="trade-metrics">
      <div><span>OPEN TRADES</span><b>{status?.open_trades ?? "—"}</b></div>
      <div><span>ALERT EVENTS</span><b>{status?.events ?? "—"}</b></div>
      <div><span>FAILED DELIVERIES</span><b>{status?.failed_deliveries ?? "—"}</b></div>
      <div><span>TELEGRAM</span><b>{status ? status.telegram_configured ? "Configured" : "Not configured" : "—"}</b></div>
    </div>
    <section className="panel monitoring-panel">
      <div className="panel-head"><div><div className="panel-kicker">CURRENT MARKET SNAPSHOT</div><h2>{symbol}</h2></div><span className="manual-tag">MANUAL REVIEW</span></div>
      <div className="monitor-snapshot"><div><small>LAST FETCHED CLOSE</small><b>{price === null ? "—" : price.toLocaleString("en-US", { maximumFractionDigits: 8 })}</b></div><div><small>CANDLE TIMESTAMP</small><b>{timestamp ? new Date(timestamp).toLocaleString() : "Unavailable"}</b></div></div>
      <button className="outline-btn" disabled={busy || price === null || !timestamp} onClick={evaluate}>{busy ? "Evaluating snapshot…" : "Evaluate snapshot against open trades"} <span>→</span></button>
      {message && <p className="analysis-empty">{message}</p>}
    </section>
    <section className="panel journal-panel">
      <div className="panel-head"><div><div className="panel-kicker">PERSISTED ALERT HISTORY</div><h2>Monitoring events</h2></div><button className="text-btn" onClick={() => refresh().catch(error => setMessage(error.message))}>Refresh ↻</button></div>
      {events.length ? <div className="monitor-events">{events.map(event => <div className="monitor-event" key={event.id}><div><b>{event.event_type.replace(/_/g, " ")}</b><small>{event.symbol} · Trade #{event.trade_id} · {new Date(event.created_at).toLocaleString()}</small></div><span className={event.delivery_status === "delivered" ? "positive" : event.delivery_status === "failed" ? "negative" : "muted"}>{event.delivery_status}</span>{(event.delivery_status === "failed" || event.delivery_status === "not_configured") && <button className="text-btn" onClick={() => retry(event.id)}>Retry</button>}</div>)}</div> : <div className="analysis-empty">No monitoring events yet. Events appear when an evaluated snapshot reaches an open trade's stop-loss or take-profit level.</div>}
    </section>
  </div>;
}
