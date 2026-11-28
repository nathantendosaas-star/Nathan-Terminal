const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
async function request<T>(path:string, init?:RequestInit):Promise<T>{
 const response=await fetch(`${API_BASE}${path}`,{...init,headers:{"Content-Type":"application/json",...(init?.headers||{})}});
 if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(typeof body?.detail==="string"?body.detail:body?.detail?.message||`Trade Desk request failed (${response.status}).`);}
 return response.json() as Promise<T>;
}
export type RiskSettings={account_equity:number;account_currency:string;risk_per_trade_pct:number;maximum_daily_loss_pct:number;maximum_simultaneous_positions:number;minimum_risk_reward:number;maximum_market_data_age_seconds:number};
export type InstrumentSpec={symbol:string;contract_multiplier:number;quantity_step:number;minimum_quantity:number;quote_currency:string;specification_note:string};
export type RiskResult={status:"APPROVED"|"REJECTED"|"NEEDS_REVIEW";reasons:string[];risk_reward?:number;risk_budget?:number;suggested_quantity?:number;suggested_risk_amount?:number;planned_risk_amount?:number;reward_amount?:number;daily_loss_limit?:number;projected_daily_loss_exposure?:number;market_data_age_seconds?:number};
export type Trade={id:number;symbol:string;direction:"LONG"|"SHORT";entry_price:number;stop_loss:number;take_profit:number;quantity:number;risk_amount:number;risk_reward:number;status:"OPEN"|"CLOSED";opened_at:string;closed_at:string|null;exit_price:number|null;realized_pnl:number|null};
export type TradePlan={symbol:string;direction:"LONG"|"SHORT";entry_price:number;stop_loss:number;take_profit:number;quantity:number|null;market_price:number;market_data_timestamp:string};
export const getRiskSettings=()=>request<RiskSettings>("/api/v1/trading/settings");
export const saveRiskSettings=(v:RiskSettings)=>request<RiskSettings>("/api/v1/trading/settings",{method:"PUT",body:JSON.stringify(v)});
export const getInstruments=()=>request<InstrumentSpec[]>("/api/v1/trading/instruments");
export const saveInstrument=(v:InstrumentSpec)=>request<InstrumentSpec>("/api/v1/trading/instruments",{method:"PUT",body:JSON.stringify(v)});
export const getTrades=()=>request<Trade[]>("/api/v1/trading/trades");
export const validateTrade=(v:TradePlan)=>request<RiskResult>("/api/v1/trading/validate",{method:"POST",body:JSON.stringify(v)});
export const registerTrade=(v:TradePlan)=>request<Trade>("/api/v1/trading/trades",{method:"POST",body:JSON.stringify(v)});
export const closeTrade=(id:number,exit_price:number)=>request<Trade>(`/api/v1/trading/trades/${id}/close`,{method:"POST",body:JSON.stringify({exit_price})});
