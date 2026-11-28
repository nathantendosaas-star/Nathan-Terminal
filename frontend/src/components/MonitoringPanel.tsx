import { useEffect, useState } from "react";

function decodeVapidKey(value: string): Uint8Array {
  const padding = "=".repeat((4 - value.length % 4) % 4);
  const raw = atob((value + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, character => character.charCodeAt(0));
}

type Props = { symbol: string; price: number | null; timestamp: string | null; source: string };
type Status = { mode: string; open_trades: number; events: number; failed_deliveries: number; push_enabled: boolean; push_devices: number; automatic_execution: boolean };
type Event = { id: number; trade_id: number; symbol: string; event_type: string; observed_price: number; delivery_status: string; created_at: string; last_error?: string | null };

export default function MonitoringPanel({ symbol, price, timestamp, source }: Props) {
  const [status, setStatus] = useState<Status | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMessage, setPushMessage] = useState("");
  const [pushDevices, setPushDevices] = useState(0);
  const [localSubscribed, setLocalSubscribed] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default");
  const refresh = async () => {
    const [s, e] = await Promise.all([fetch("/api/v1/monitoring/status"), fetch("/api/v1/monitoring/events")]);
    if (!s.ok || !e.ok) throw new Error("Monitoring service unavailable.");
    setStatus(await s.json());
    setEvents(await e.json());
    const push = await fetch("/api/v1/push/status");
    if (push.ok) { const p = await push.json(); setPushDevices(p.active_devices || 0); }
    setPermission("Notification" in window ? Notification.permission : "unsupported");
    if ("serviceWorker" in navigator) {
      const registration = await navigator.serviceWorker.getRegistration("/");
      const subscription = await registration?.pushManager.getSubscription();
      setLocalSubscribed(Boolean(subscription));
    }
  };
  useEffect(() => { refresh().catch(error => setMessage(error.message)); }, []);
  const enablePush = async () => {
    setPushBusy(true); setPushMessage("");
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
        throw new Error("This browser does not support Web Push. Try Chrome or another supported browser.");
      }
      const granted = await Notification.requestPermission();
      setPermission(granted);
      if (granted !== "granted") throw new Error(granted === "denied" ? "Notifications are blocked in browser settings. Allow notifications for this site, then try again." : "Notification permission was not granted.");
      const registration = await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;
      const keyResponse = await fetch("/api/v1/push/public-key");
      const keyBody = await keyResponse.json();
      if (!keyResponse.ok) throw new Error(keyBody.detail || "Unable to load notification configuration.");
      const subscription = await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: decodeVapidKey(keyBody.public_key) as BufferSource,
      });
      const response = await fetch("/api/v1/push/subscribe", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...subscription.toJSON(), device_name: navigator.userAgent.slice(0, 80) || "This device" }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Unable to save this device.");
      setLocalSubscribed(true);
      setPushDevices(body.active_devices || 1);
      setPushMessage("Phone notifications are enabled on this device.");
      await refresh();
    } catch (error) { setPushMessage(error instanceof Error ? error.message : "Unable to enable notifications."); }
    finally { setPushBusy(false); }
  };
  const disablePush = async () => {
    setPushBusy(true); setPushMessage("");
    try {
      const registration = await navigator.serviceWorker.getRegistration("/");
      const subscription = await registration?.pushManager.getSubscription();
      if (subscription) {
        const response = await fetch("/api/v1/push/unsubscribe", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
        if (!response.ok) throw new Error("Unable to remove this device from the notification list.");
        await subscription.unsubscribe();
      }
      setLocalSubscribed(false);
      await refresh();
      setPushMessage("Notifications disabled on this device.");
    } catch (error) { setPushMessage(error instanceof Error ? error.message : "Unable to disable notifications."); }
    finally { setPushBusy(false); }
  };
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
    <section className="panel push-settings"><div><div className="panel-kicker">PHONE NOTIFICATIONS</div><h2>{pushDevices ? "Web Push is enabled" : "Enable alerts on this device"}</h2><p>{pushDevices ? `${pushDevices} device subscription(s) are registered for this terminal.` : "Install Nathan Terminal as a PWA, then allow notifications to receive trade and thesis alerts when the app is closed."}</p>{pushMessage && <small className="push-message">{pushMessage}</small>}{permission === "denied" && <small className="push-message">Notifications are blocked in browser settings. Change the site permission and reload.</small>}</div><button className="outline-btn" disabled={pushBusy || permission === "unsupported"} onClick={localSubscribed ? disablePush : enablePush}>{pushBusy ? "Please wait…" : localSubscribed ? "Disable on this device" : "Enable phone notifications"}</button></section>
    <div className="notice"><b>Snapshot-driven monitoring</b> — evaluates the latest fetched candle only when you request a check. It does not run a background price watcher, close trades, or place orders.</div>
    <div className="trade-metrics">
      <div><span>OPEN TRADES</span><b>{status?.open_trades ?? "—"}</b></div>
      <div><span>ALERT EVENTS</span><b>{status?.events ?? "—"}</b></div>
      <div><span>FAILED DELIVERIES</span><b>{status?.failed_deliveries ?? "—"}</b></div>
      <div><span>PUSH DEVICES</span><b>{status?.push_devices ?? "—"}</b></div>
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
