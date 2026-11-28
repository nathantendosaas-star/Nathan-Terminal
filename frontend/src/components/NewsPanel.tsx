import { useEffect, useState } from "react";

type NewsItem = { title: string; url: string | null; source: string; published_at: string | null; summary: string };
type NewsResponse = { provider: string; fetched_at: string; items: NewsItem[]; disclaimer: string };

export default function NewsPanel() {
  const [query, setQuery] = useState("financial markets OR bitcoin OR stocks");
  const [data, setData] = useState<NewsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const load = async (q = query) => {
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/v1/news?${new URLSearchParams({ q, limit: "30" })}`);
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "News feed unavailable.");
      setData(body);
    } catch (err) { setError(err instanceof Error ? err.message : "News feed unavailable."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  return <div className="news-workspace">
    <section className="panel news-search-panel">
      <div className="panel-kicker">MARKET INTELLIGENCE FEED</div>
      <form className="news-search" onSubmit={event => { event.preventDefault(); load(); }}>
        <input aria-label="News search" value={query} maxLength={120} onChange={event => setQuery(event.target.value)} />
        <button className="outline-btn" type="submit" disabled={loading || query.trim().length < 2}>{loading ? "Searching…" : "Search headlines"}</button>
      </form>
      {data && <small className="news-meta">{data.provider} · Fetched {new Date(data.fetched_at).toLocaleString()} · {data.items.length} stories</small>}
      {error && <p className="analysis-empty error">{error}</p>}
    </section>
    <section className="news-list">{data?.items.map((item, index) => <article className="panel news-item" key={item.url || index}>
      <div className="panel-kicker">{item.source} {item.published_at ? `· ${new Date(item.published_at).toLocaleString()}` : ""}</div>
      <h2>{item.url ? <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a> : item.title}</h2>
      <p dangerouslySetInnerHTML={{ __html: item.summary }} />
    </article>)}</section>
    <p className="analysis-disclaimer">{data?.disclaimer || "Headlines are research context. Verify important information with the original publisher."}</p>
  </div>;
}
