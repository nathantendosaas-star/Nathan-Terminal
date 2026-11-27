export type GeminiAnalysisResponse = {
  symbol: string;
  interval: string;
  source: string;
  model: string;
  generated_at: string;
  candles_analyzed: number;
  technical_analysis: unknown;
  analysis: string;
  disclaimer: string;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export async function fetchGeminiStatus(): Promise<{configured:boolean;model:string;provider:string}> {
  const response = await fetch(`${API_BASE}/api/v1/analysis/status`);
  if (!response.ok) throw new Error(`AI Analyst status unavailable (${response.status}).`);
  return response.json();
}

export async function requestGeminiAnalysis(
  symbol: string,
  interval: string,
  provider: "binance" | "twelvedata",
  question: string,
): Promise<GeminiAnalysisResponse> {
  const response = await fetch(`${API_BASE}/api/v1/analysis`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({symbol, interval, provider, question}),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Gemini analysis failed (${response.status}).`);
  }
  return response.json() as Promise<GeminiAnalysisResponse>;
}
