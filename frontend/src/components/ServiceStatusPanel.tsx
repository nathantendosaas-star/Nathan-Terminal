import { useCallback, useEffect, useState } from "react";

type ServiceState = "checking" | "online" | "configured" | "unavailable" | "not-configured" | "error";
type Service = { name: string; detail: string; state: ServiceState };
const API = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function readStatus(path: string) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export default function ServiceStatusPanel() {
  const [services, setServices] = useState<Service[]>([
    { name: "Backend API", detail: "Checking health endpoint", state: "checking" },
    { name: "Supabase PostgreSQL", detail: "Checking authenticated database-backed session endpoint", state: "checking" },
    { name: "Gemini", detail: "Checking server-side configuration", state: "checking" },
    { name: "Kronos-mini", detail: "Checking forecasting runtime", state: "checking" },
  ]);
  const [checkedAt, setCheckedAt] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    setBusy(true);
    const results = await Promise.allSettled([
      readStatus("/health"),
      readStatus("/api/v1/sessions/current"),
      readStatus("/api/v1/analysis/status"),
      readStatus("/api/v1/forecasts/status"),
    ]);
    const [backend, database, gemini, kronos] = results;
    const next: Service[] = [
      { name: "Backend API", state: backend.status === "fulfilled" ? "online" : "unavailable", detail: backend.status === "fulfilled" ? `Healthy · ${backend.value.version ?? "API responding"}` : backend.reason instanceof Error ? backend.reason.message : "Health check failed" },
      { name: "Supabase PostgreSQL", state: database.status === "fulfilled" ? "online" : "unavailable", detail: database.status === "fulfilled" ? "Database-backed session endpoint responded" : database.reason instanceof Error ? database.reason.message : "Database check failed" },
      { name: "Gemini", state: gemini.status === "fulfilled" ? (gemini.value.configured ? "configured" : "not-configured") : "error", detail: gemini.status === "fulfilled" ? (gemini.value.configured ? `API key configured · ${gemini.value.model}` : "GEMINI_API_KEY is not configured") : "Gemini status endpoint unavailable" },
      { name: "Kronos-mini", state: kronos.status === "fulfilled" ? (kronos.value.loaded ? "online" : "unavailable") : "error", detail: kronos.status === "fulfilled" ? (kronos.value.loaded ? `Loaded · ${kronos.value.model} · ${kronos.value.device || "device unknown"}` : kronos.value.error || "Model not loaded; optional runtime is not currently active") : "Kronos status endpoint unavailable" },
    ];
    setServices(next);
    setCheckedAt(new Date().toLocaleTimeString());
    setBusy(false);
  }, []);
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 30000); return () => window.clearInterval(timer); }, [refresh]);
  return <div className="service-status-panel">
    <section className="panel service-status-card">
      <div className="panel-head"><div><div className="panel-kicker">SYSTEM HEALTH</div><h2>Service connections</h2></div><button className="outline-btn service-refresh" disabled={busy} onClick={() => void refresh()}>{busy ? "Checking…" : "Refresh status ↻"}</button></div>
      <p className="service-status-intro">Live checks refresh every 30 seconds. Database status is inferred from a database-backed API request. Gemini reports key configuration, not a live model-generation test.</p>
      <div className="service-grid">{services.map(service => <div className="service-row" key={service.name}><span className={`service-dot ${service.state}`}/><div><b>{service.name}</b><small>{service.detail}</small></div><strong className={`service-state ${service.state}`}>{service.state === "online" ? "ONLINE" : service.state === "configured" ? "CONFIGURED" : service.state === "not-configured" ? "NOT SET" : service.state === "checking" ? "CHECKING" : service.state === "unavailable" ? "UNAVAILABLE" : "ERROR"}</strong></div>)}</div>
      <div className="service-checked">Last checked: {checkedAt || "Checking…"}</div>
    </section>
    <section className="panel service-status-card"><div className="panel-kicker">APPLICATION CONFIGURATION</div><h2>Deployment settings</h2><div className="service-config-list"><div><b>Frontend</b><span>Vercel · VITE_API_BASE_URL</span></div><div><b>Backend</b><span>Render · HTTPS API</span></div><div><b>Database</b><span>Supabase PostgreSQL · private app schema</span></div><div><b>Trading execution</b><span>Manual only · no broker order placement</span></div></div></section>
  </div>;
}
