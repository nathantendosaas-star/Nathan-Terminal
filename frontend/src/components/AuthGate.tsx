import { FormEvent, useEffect, useState } from "react";
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
type AuthStatus = { auth_required: boolean; authenticated: boolean };

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [required, setRequired] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const token = sessionStorage.getItem("nt_access_token") || "";
    fetch(API_BASE + "/api/v1/auth/status", { headers: token ? { Authorization: "Bearer " + token } : {} })
      .then(response => { if (!response.ok) throw new Error("Unable to verify terminal access."); return response.json() as Promise<AuthStatus>; })
      .then(status => { if (!active) return; setRequired(status.auth_required); if (status.auth_required && !status.authenticated) sessionStorage.removeItem("nt_access_token"); setReady(true); })
      .catch(() => { if (active) { setError("Backend unavailable. Check the API service and try again."); setReady(true); } });
    return () => { active = false; };
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch(API_BASE + "/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Login failed.");
      sessionStorage.setItem("nt_access_token", body.access_token); setPassword(""); window.location.reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Login failed."); }
    finally { setBusy(false); }
  };
  if (!ready) return <div className="auth-screen"><div className="auth-card">SECURELY CONNECTING TO NATHAN TERMINAL…</div></div>;
  if (!required) return <>{children}</>;
  if (sessionStorage.getItem("nt_access_token")) return <div className="auth-app">
    <button className="auth-lock" onClick={() => { sessionStorage.removeItem("nt_access_token"); window.location.reload(); }}>Lock terminal</button>
    {children}
  </div>;
  return <div className="auth-screen"><form className="auth-card" onSubmit={submit}>
    <div className="auth-mark">N</div><div className="auth-kicker">PRIVATE WORKSPACE</div><h1>Nathan Terminal</h1>
    <p>Enter your password to access your personal market intelligence terminal.</p>
    <label htmlFor="terminal-password">PASSWORD</label>
    <input id="terminal-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required autoFocus />
    {error && <div className="auth-error">{error}</div>}
    <button type="submit" disabled={busy || !password}>{busy ? "Verifying…" : "Unlock terminal"}</button>
    <small>Private access · Sessions expire after 12 hours</small>
  </form></div>;
}
