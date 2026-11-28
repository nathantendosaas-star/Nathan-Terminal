import { useEffect, useState } from "react";

type Trade = { id: number; symbol: string; direction: string; entry_price: number; status: string };
type Review = { reassessment_id: number; status: string; assessment: string; changes: string[]; supporting_evidence: string[]; contradicting_evidence: string[]; missing_evidence: string[]; confidence: number; created_at: string; alert_created: boolean; disclaimer: string };
type History = { original_thesis: { original_thesis: string; original_analysis: string } | null; reassessments: Array<{id:number;status:string;assessment:string;created_at:string}>; alerts: Array<{status:string;created_at:string}> };

export default function ThesisReviewPanel() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [tradeId, setTradeId] = useState("");
  const [originalThesis, setOriginalThesis] = useState("");
  const [originalAnalysis, setOriginalAnalysis] = useState("");
  const [provider, setProvider] = useState("binance");
  const [interval, setInterval] = useState("1h");
  const [review, setReview] = useState<Review | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const selected = trades.find(t => String(t.id) === tradeId);
  const loadTrades = async () => {
    const response = await fetch("/api/v1/trading/trades?status=OPEN");
    if (!response.ok) throw new Error("Unable to load open trades.");
    const items: Trade[] = await response.json();
    setTrades(items);
    if (!tradeId && items.length) setTradeId(String(items[0].id));
  };
  const loadHistory = async (id: string) => {
    const response = await fetch(`/api/v1/thesis/trades/${id}/history`);
    if (!response.ok) throw new Error("Unable to load thesis history.");
    const data: History = await response.json();
    setHistory(data);
    if (data.original_thesis) {
      setOriginalThesis(data.original_thesis.original_thesis);
      setOriginalAnalysis(data.original_thesis.original_analysis);
    } else {
      setOriginalThesis("");
      setOriginalAnalysis("");
    }
  };
  useEffect(() => { loadTrades().catch(e => setMessage(e.message)); }, []);
  useEffect(() => { if (tradeId) loadHistory(tradeId).catch(e => setMessage(e.message)); else setHistory(null); }, [tradeId]);
  const reassess = async () => {
    if (!tradeId) return;
    setBusy(true); setMessage(""); setReview(null);
    try {
      const response = await fetch(`/api/v1/thesis/trades/${tradeId}/reassess`, {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({original_thesis: originalThesis || null, original_analysis: originalAnalysis || null, provider, interval, include_news: true}),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "Thesis reassessment failed.");
      setReview(body);
      await loadHistory(tradeId);
    } catch (e) { setMessage(e instanceof Error ? e.message : "Thesis reassessment failed."); }
    finally { setBusy(false); }
  };
  return <div className="thesis-workspace">
    <div className="notice"><b>AI thesis audit</b> — compares the saved original thesis with fresh provider candles, calculated indicators and available headlines. It is advisory only: no trade is edited, closed or executed.</div>
    <section className="panel thesis-panel">
      <div className="panel-head"><div><div className="panel-kicker">OPEN MANUAL TRADES</div><h2>Choose a trade to review</h2></div><span className="manual-tag">HUMAN DECISION</span></div>
      {trades.length ? <>
        <div className="thesis-controls">
          <label>OPEN TRADE<select value={tradeId} onChange={e=>setTradeId(e.target.value)}>{trades.map(t=><option key={t.id} value={t.id}>#{t.id} · {t.symbol} · {t.direction} · {t.entry_price}</option>)}</select></label>
          <label>DATA PROVIDER<select value={provider} onChange={e=>setProvider(e.target.value)}><option value="binance">Binance</option><option value="twelvedata">Twelve Data</option></select></label>
          <label>TIMEFRAME<select value={interval} onChange={e=>setInterval(e.target.value)}>{["15m","30m","1h","4h","1d"].map(v=><option key={v}>{v}</option>)}</select></label>
        </div>
        <label className="thesis-field">ORIGINAL TRADE THESIS<textarea value={originalThesis} onChange={e=>setOriginalThesis(e.target.value)} disabled={!!history?.original_thesis} placeholder="What market structure, catalyst or condition justified this trade?" /></label>
        <label className="thesis-field">ORIGINAL GEMINI ANALYSIS<textarea value={originalAnalysis} onChange={e=>setOriginalAnalysis(e.target.value)} disabled={!!history?.original_thesis} placeholder="Paste the original analysis that informed this trade." /></label>
        {history?.original_thesis && <p className="thesis-help">The original thesis is locked after first save so every reassessment uses the same baseline.</p>}
        <button className="outline-btn" disabled={busy || !selected || originalThesis.trim().length < 10 || originalAnalysis.trim().length < 10} onClick={reassess}>{busy ? "Reassessing thesis with Gemini…" : "Reassess trade thesis"} <span>→</span></button>
      </> : <div className="analysis-empty">No open manual trades are available. Register an approved trade in Trade Desk first.</div>}
      {message && <div className="analysis-empty error">{message}</div>}
    </section>
    {review && <section className="panel thesis-result">
      <div className="panel-head"><div><div className="panel-kicker">LATEST GEMINI ASSESSMENT</div><h2>{review.status.replace(/_/g," ")} <span className="live-pill">{Math.round(review.confidence*100)}% CONFIDENCE</span></h2></div></div>
      <p>{review.assessment}</p>
      <div className="thesis-evidence-grid">
        <div><b>WHAT CHANGED</b>{review.changes.map((x,i)=><p key={i}>{x}</p>)}</div>
        <div><b>SUPPORTING EVIDENCE</b>{review.supporting_evidence.map((x,i)=><p key={i}>{x}</p>)}</div>
        <div><b>CONTRADICTING EVIDENCE</b>{review.contradicting_evidence.length?review.contradicting_evidence.map((x,i)=><p key={i}>{x}</p>):<p>None cited.</p>}</div>
        <div><b>MISSING EVIDENCE</b>{review.missing_evidence.length?review.missing_evidence.map((x,i)=><p key={i}>{x}</p>):<p>None reported.</p>}</div>
      </div>
      {review.alert_created && <p className="thesis-alert">A thesis status alert was recorded. Check Monitoring for delivery status.</p>}
      <p className="analysis-disclaimer">{review.disclaimer}</p>
    </section>}
    <section className="panel thesis-panel">
      <div className="panel-head"><div><div className="panel-kicker">AUDIT TRAIL</div><h2>Reassessment history</h2></div></div>
      {history?.reassessments.length ? <div className="monitor-events">{history.reassessments.map(item=><div className="monitor-event" key={item.id}><div><b>{item.status.replace(/_/g," ")}</b><small>{item.assessment} · {new Date(item.created_at).toLocaleString()}</small></div></div>)}</div> : <div className="analysis-empty">No reassessments recorded for this trade yet.</div>}
    </section>
  </div>;
}
