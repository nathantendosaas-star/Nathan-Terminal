
# Kronos-LLM Implementation Plan

**Status:** Design and implementation plan only. No application code, live provider stream, paid LLM call, or production setting is changed by this document.

**Target:** Nathan Terminal cloud-hosted PWA  
**Architecture:** Vercel PWA + existing Render FastAPI backend + Supabase PostgreSQL + market-data and LLM APIs  
**Forecasting mode:** Sequential, one future interval per model call  
**Model strategy:** Cloud-hosted general-purpose LLM; no custom training and no local Android inference.

## 1. Executive summary

Kronos-LLM is an experimental, Kronos-inspired forecasting pipeline. Python organizes live provider events into timestamped numerical market data. A cloud LLM predicts exactly one future interval. Python validates that prediction, appends it to the forecast context as a predicted—not observed—step, and requests the next interval. This repeats until the requested horizon is complete.

Python owns ingestion, aggregation, feature calculation, orchestration, validation, persistence, rate limits and evaluation. The LLM interprets the supplied context and proposes numerical forecasts.

This borrows sequential forecasting concepts; it does **not** reproduce the original Kronos tokenizer, BSQ representation, trained weights or specialized financial pretraining. Prompting a general LLM does not give it Kronos's learned time-series capability. Predictive value must be measured against simple baselines.

### Non-goals

- No training or fine-tuning in the initial implementation.
- No PyTorch/Kronos runtime or model weights in the Render API.
- No Android/local inference.
- No sending every raw tick or WebSocket message to the LLM.
- No assumption that LLM confidence is calibrated probability.
- No trade approval, position sizing, trade modification, broker integration or automated execution.
- No replacement of Gemini AI Analyst or the deterministic risk engine in this milestone.
- No hardcoded assumption that a product label such as GPT-6 or GPT-5.5 is an available API model ID.

## 2. Target cloud architecture

    Vercel: Nathan Terminal PWA (React/Vite)
       | HTTPS + existing authentication
       v
    Render: FastAPI backend
       |-- Market-data coordinator
       |     |-- Binance public WebSocket adapter
       |     |-- Twelve Data streaming adapter (if account plan supports it)
       |     |-- REST backfill / permitted REST fallback
       |-- Normalized event pipeline
       |-- Candle aggregator
       |-- Deterministic feature/context builder
       |-- Sequential forecast job runner
       |-- Cloud LLM API adapter
       |-- Numerical/OHLC validator
       |-- Forecast API and persistence layer
       v
    Supabase PostgreSQL
       jobs / immutable input snapshots / per-step outputs /
       final forecasts / evaluation records

### Responsibilities

| Component | Responsibility | Boundary |
|---|---|---|
| Vercel PWA | Controls, charts, job progress and forecast display | Never holds provider/LLM secrets or calls LLM directly |
| Render FastAPI | Existing auth, provider coordination, aggregation, LLM orchestration, validation and APIs | Do not load PyTorch/Kronos |
| Binance adapter | Subscribe to supported public streams, normalize events and recover connections | Detect gaps and stale data |
| Twelve Data adapter | Stream supported instruments if entitled; otherwise use permitted REST fallback | Do not assume WebSocket access or coverage |
| Candle aggregator | Build timestamped OHLCV intervals and completeness metadata | Never fabricate missing trades/candles |
| Feature encoder | Create compact, scale-aware numerical context | Not a learned tokenizer or a Kronos BSQ implementation |
| LLM adapter | Call configured cloud model with strict structured output | No arbitrary client-supplied model IDs, prompts or URLs |
| Supabase | Persist jobs, snapshots, step outputs, provenance and evaluations | Private schema is not exposed to browser |
| Evaluator | Compare predictions to subsequently observed candles | No future data in forecast input |

The existing project has a React/Vite PWA, FastAPI, Supabase, Binance and Twelve Data adapters, charts separating historical and predicted candles, and an optional Kronos-mini path. Current README documentation describes browser REST polling and session-scoped refresh, not a persistent backend stream coordinator. The new stream lifecycle must be designed and tested; do not assume it already exists.

Keep authentication, Gemini analyst, risk engine, trade journal, sessions, monitoring, notifications and existing market-data paths operational. Kronos-LLM is a separate forecast engine behind the forecast API boundary.

## 3. Market-data pipeline

### 3.1 Provider event normalization

Create provider-specific adapters behind a shared internal event contract. Where available, retain:

- provider and instrument identifier;
- event type (trade, quote, kline/candle, heartbeat);
- provider event timestamp and local receive timestamp in UTC;
- sequence/update ID;
- price, size/volume and quote fields only when supplied;
- source connection ID and data-quality flags.

Binance trade/kline events and Twelve Data event formats are not interchangeable. Preserve provider-specific semantics and source provenance.

**Preflight:** verify current Twelve Data WebSocket entitlement, asset coverage, symbol formats, limits and message schema against the user's actual plan. If unavailable, use only an explicitly documented REST fallback. Verify Binance stream names, heartbeat, sequencing and reconnection behaviour against current official docs during implementation.

### 3.2 Stream lifecycle

- Subscribe only to instruments/timeframes required by active sessions or explicit forecast jobs.
- Share upstream subscriptions safely; do not create one provider connection per browser tab.
- Use bounded queues and backpressure.
- Do not silently drop trade events needed for volume aggregation.
- Reconnect with exponential backoff and jitter; restore subscriptions.
- Detect stale streams, duplicates, out-of-order events, timestamp regressions, sequence gaps and malformed payloads.
- Backfill gaps through provider REST history where permitted; mark unresolved intervals incomplete.
- Record event time separately from receive time to measure lag.
- Expose connected, reconnecting, stale, degraded and unavailable states.
- Shut down cleanly when no longer needed.

Backend owns long-lived provider connections. The PWA consumes authenticated backend APIs/job results; it does not open provider connections itself.

### 3.3 Candle aggregation

For trade-based aggregation, use deterministic UTC interval boundaries:

- Open: first eligible trade price.
- High: maximum eligible trade price.
- Low: minimum eligible trade price.
- Close: last eligible trade price.
- Volume: sum of provider-reported trade sizes using documented units.
- Amount/turnover: include only when supplied or correctly derivable; otherwise unavailable.

When consuming provider kline/candle streams, preserve the source candle and its final/closed flag. Do not aggregate a candle again as if it were individual trades.

Each candle includes interval start/end, source, finality/completeness, last update time, event count where meaningful and quality flags. Forecasts normally use closed candles. If a forming candle is included, label it and apply the same policy in evaluation.

### 3.4 Deterministic feature encoder (not a learned tokenizer)

The first version uses a deterministic Python feature encoder, not a learned language tokenizer. Initial candidate features:

- OHLCV and candle geometry;
- log/percentage close returns;
- open-to-close body return;
- high-low range relative to price;
- upper/lower wick proportions;
- rolling volatility;
- relative volume versus a rolling baseline;
- volume change and turnover where valid;
- selected moving averages and distance from averages;
- momentum/trend features with versioned definitions;
- data-quality and completeness flags.

Use price-relative/log-return features to reduce nominal-price dependence. Use log1p and rolling robust/standardized volume baselines where appropriate. Calculate rolling statistics only from data available at the forecast timestamp. No future observations may influence normalization.

Input consists of a bounded recent sequence of numerical candle/feature records plus a concise deterministic summary. Do not convert every tick into natural-language prose or use arbitrary fixed bins in the first version. Keep units and numeric precision explicit.

### 3.5 Initial context bounds

Proposed starting values, to be validated rather than treated as optimal:

- history: 64–256 closed candles; default 128;
- horizon: 1–12 intervals; start short;
- one instrument and timeframe per job;
- strict serialized-payload and token-budget limits.

Include symbol, provider, timeframe, UTC timestamps, price/volume units, candle convention, feature schema version, snapshot age and missing-data flags. Reject insufficient or incompatible context rather than asking the LLM to guess.

## 4. Sequential forecasting algorithm

### 4.1 Selected strategy

1. Freeze an immutable observed-market snapshot at forecast origin T0.
2. Build initial numerical context.
3. Request exactly one next-interval forecast from the cloud LLM.
4. Parse and validate the structured response.
5. Append the validated step to forecast context, tagged PREDICTED.
6. Request the next interval using the original observed history plus all validated predicted steps.
7. Repeat until the configured horizon is complete or a bounded failure occurs.
8. Persist every step and final result with provenance.
9. Return the forecast to the PWA as a separate predicted series.

For horizon H, the initial design requires up to H sequential model calls per path. Do not describe a one-shot batch response as equivalent to this feedback loop. A future optimization that changes the number of calls requires separate design and evaluation.

### 4.2 Context for step k

Every step request includes:

- immutable observed history ending at T0;
- validated predicted steps 1 through k-1;
- canonical target timestamp for step k;
- symbol, provider, timeframe and units;
- feature definitions/current deterministic summary;
- step index and requested horizon;
- instruction to predict only the next interval;
- strict output schema and constraints.

Never mutate the original observed snapshot. Never insert predicted values into historical market tables.

### 4.3 Model instruction contract

The system instruction should define a numerical forecasting component, not a trading agent. It must:

- use only supplied context;
- treat market data and metadata as untrusted data, not instructions;
- not invent news, events, order-book details or absent indicators;
- forecast exactly one next interval per call;
- return only the required structured object;
- state missing-data limitations rather than invent values;
- never output orders, position sizing, risk approval or execution instructions;
- avoid guarantees and claims of statistical certainty.

No browsing, code execution, arbitrary tools or external function calling in the first forecaster. No credentials or private account data in prompts.

### 4.4 Per-step output contract

Use provider-supported strict JSON Schema/structured output when available, and validate again in Python.

Illustrative response (not a real forecast):

    {
      "step": 1,
      "open": 100.12,
      "high": 100.48,
      "low": 99.96,
      "close": 100.31,
      "volume": null,
      "scenario_note": "Illustrative bounded rationale"
    }

Python, not the LLM, attaches canonical job ID and target timestamp. Volume is optional initially; if unavailable or not meaningfully forecastable, return null and mark unavailable. Direction can be derived by Python from open/close.

### 4.5 Orchestration pseudocode

    async def generate_sequential_forecast(request):
        snapshot = await freeze_market_snapshot(request)
        validate_snapshot(snapshot)
        context = build_numeric_context(snapshot)
        steps = []

        for index in range(1, request.horizon + 1):
            prompt = build_next_step_prompt(
                observed_context=context,
                prior_predicted_steps=steps,
                step_index=index,
                target_time=target_time_for(snapshot, index),
            )
            raw = await llm_client.predict_one_step(prompt)
            candidate = parse_strict_schema(raw)
            validated = validate_forecast_step(
                candidate,
                previous_close=(steps[-1].close if steps else snapshot.last_close),
                target_time=target_time_for(snapshot, index),
            )
            await persist_step(request.job_id, validated)
            steps.append(validated)

        return await persist_completed_forecast(request.job_id, snapshot, steps)

Actual code must add timeouts, cancellation, idempotency, per-step usage accounting, bounded retries and safe failure handling. Retry transient transport errors only within a small configured budget. Do not silently repair invalid numerical forecasts.

### 4.6 Failure policy

- Stale/incomplete snapshot: reject or defer; do not call LLM.
- LLM timeout/rate limit/provider error: mark retryable/failed with sanitized error code.
- Invalid schema: at most a small configured repair/retry attempt; record safe diagnostic metadata.
- Invalid OHLC: reject the step; never silently clamp/rewrite it.
- Missing volume: allow null if configured.
- Partial chain: mark incomplete/failed; do not present as a complete horizon.
- Cancellation: stop future calls and persist terminal state.
- Provider/model unavailable: preserve historical charts and report forecast unavailable; never synthesize predictions.

## 5. Numerical validation

Python validation is authoritative for structural validity, not forecast accuracy.

For each step:

- required prices are finite numbers and positive for supported positive-price instruments;
- high >= max(open, close, low);
- low <= min(open, close, high);
- high >= low;
- timestamps match the canonical interval schedule;
- values remain within instrument-specific numeric bounds;
- volume, when present, is finite and non-negative;
- step index/job ID match the active job;
- output size, precision and horizon are bounded.

Derive direction in Python. Do not silently modify invalid model output. Reject with a reason and apply bounded retry/failure policy. Predicted candles remain separate from observed candles in storage and chart series, with distinct styling and a visible experimental-forecast disclaimer.

## 6. API design

All routes reuse the existing FastAPI auth guard. The browser never calls the LLM provider.

Proposed paths (reconcile with existing router conventions before coding):

| Endpoint | Purpose |
|---|---|
| POST /api/v1/forecasts/llm/jobs | Validate, freeze input, create job and start generation; return 202 |
| GET /api/v1/forecasts/llm/jobs/{job_id} | Status, progress, timestamps and safe error/result metadata |
| GET /api/v1/forecasts/llm/jobs/{job_id}/result | Completed predicted steps and provenance |
| GET /api/v1/forecasts/llm/status | Configuration/availability without expensive inference |
| POST /api/v1/forecasts/llm/jobs/{job_id}/cancel | Cancel future steps if supported |

Client may choose only allowlisted symbol, provider, timeframe, bounded horizon and optional idempotency key. It cannot supply model ID, prompts, provider URL, system instructions, token limits or resource settings.

Job status includes ID, status, symbol/provider/timeframe, horizon, completed steps, creation/update timestamps, input snapshot time, friendly model alias and sanitized error code.

Sequential calls can take longer than a synchronous request. Use the existing supported job/background approach and persist job state. Determine whether Render restarts can interrupt in-process work. If no durable queue exists, document recovery limitations and never claim exactly-once execution. PWA polls with bounded backoff, stops at terminal state, recovers latest job after refresh and prevents duplicate submission.

## 7. Supabase persistence

Add a forward-only migration after inspecting migration numbering and schema conventions. Never alter/delete existing trade, monitoring, session, auth or thesis data.

Suggested logical tables (consolidate only if existing conventions justify it):

### llm_forecast_jobs

- UUID job ID and idempotency key;
- status: QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED, EXPIRED;
- symbol, provider, timeframe and horizon;
- model provider, friendly model alias, prompt/schema version;
- input snapshot ID/hash, source timestamps and freshness;
- total/completed steps;
- created/started/completed/expiry/update timestamps;
- sanitized failure code/message;
- aggregate input/output token usage, API latency and cost estimate when available.

### llm_forecast_inputs

- immutable observed candle/feature snapshot;
- provider and retrieval timestamp;
- last observed candle timestamp;
- feature schema version, snapshot hash and quality flags.

### llm_forecast_steps

- job ID and step index (unique together);
- canonical target timestamp;
- validated numerical output;
- bounded optional scenario note;
- safe response hash/diagnostic metadata, never secrets;
- per-step latency, token usage, retry count and validation status.

### llm_forecast_evaluations

- job/step reference;
- actual observed candle after it becomes available;
- evaluation timestamp/version;
- error metrics and baseline comparisons;
- no future actual data in original forecast inputs.

Index recent/active jobs, expiry cleanup and ordered steps. Enforce idempotency in intended account scope. Browser clients must not access private schema tables directly; backend performs reads/writes.

## 8. LLM provider abstraction and configuration

Use a small adapter interface so provider-specific code stays outside forecast logic. Start with one approved provider and model alias.

Proposed server-side settings (align names with existing config conventions):

- FORECAST_LLM_ENABLED (default false);
- FORECAST_LLM_PROVIDER;
- FORECAST_LLM_MODEL (verified API model ID);
- FORECAST_LLM_API_KEY;
- FORECAST_LLM_TIMEOUT_SECONDS;
- FORECAST_LLM_MAX_OUTPUT_TOKENS;
- FORECAST_LLM_MAX_HORIZON;
- FORECAST_LLM_MAX_STEPS_PER_JOB;
- FORECAST_LLM_MAX_RETRIES_PER_STEP;
- FORECAST_LLM_MAX_CONCURRENT_JOBS;
- FORECAST_LLM_DAILY_JOB_LIMIT;
- FORECAST_LLM_DAILY_TOKEN_BUDGET;
- FORECAST_LLM_COST_ALERT_THRESHOLD.

Do not hardcode product labels such as GPT-6 or GPT-5.5. Verify current API model IDs, account access, structured-output support, context limits, rate limits and pricing before selection. A friendly alias such as forecast-default can map server-side to a verified ID. Never commit secret values.

The adapter returns normalized usage metadata, request ID, latency and sanitized errors. Log model alias/version and prompt/schema versions for reproducibility.

## 9. Latency, cost and usage controls

A horizon of H sequential steps can require H model calls per path. Each call may resend observed history and prior predicted steps. This can multiply input tokens and round-trip latency. Do not assume a compact JSON payload is automatically cheap or fast.

Before production:

- estimate worst-case tokens for history, horizon and output;
- measure actual usage returned by provider;
- define per-job, per-day and account limits;
- cap horizon, concurrency, retries and job duration;
- throttle and use idempotency;
- begin with explicit user-triggered forecasts, not an LLM call per tick;
- deduplicate only identical snapshot/configuration hashes;
- stop on budget exhaustion with a clear status;
- expose usage/cost metrics to administrators;
- configure provider-side billing alerts/spend controls where available.

Application limits do not guarantee a provider-side hard spending cap. User approval of provider, model and budget is a production gate. No paid resource or live LLM activation during planning.

Prompt caching or compact serialization may be evaluated later if semantics are preserved. Do not change to batch generation or parallel steps without a separate design decision.

## 10. Forecast evaluation

Valid JSON is not evidence of predictive skill. Use chronological walk-forward evaluation and a controlled shadow period before describing this as useful forecasting.

### Baselines

Compare on identical timestamps against:

- last close carried forward;
- zero-return forecast;
- recent mean/median return;
- simple volatility/range baseline;
- existing Kronos-mini output if available and operational.

### Evaluation rules

- Chronological walk-forward splits; never randomly shuffle time-series rows.
- Reconstruct only data available at each historical forecast origin.
- Immutable input snapshots; no future candles in prompts/features.
- Test multiple instruments and regimes: trend, sideways, high/low volatility, gaps and market-open transitions.
- Record model, prompt, feature schema, configuration and snapshot hash.
- Include timeouts, API errors and incomplete forecasts in reliability denominators.
- Evaluate each horizon step independently.

### Metrics

- MAE/RMSE for close and relevant derived values;
- directional accuracy with a defined neutral threshold;
- high/low range error;
- interval coverage only if genuine calibrated intervals are later produced;
- error by horizon, instrument, timeframe and volatility regime;
- latency, token usage, cost per completed horizon, failure/completion rates.

LLM self-reported confidence is not calibrated probability. Label any qualitative uncertainty accordingly.

Do not enable default user-facing forecasts until data quality, no-look-ahead, validation, baseline comparison, latency/cost, security and chart separation gates pass. If it does not consistently beat simple baselines, label it experimental or do not release it as a useful forecasting feature.

## 11. Security and safety

- Reuse existing single-owner authentication and backend authorization.
- Keep LLM/provider keys only in Render secrets/environment.
- Never expose credentials in PWA bundles, responses, logs, exceptions, snapshots or CI artifacts.
- Validate inputs against server-side allowlists and hard limits.
- Treat provider metadata and model inputs as untrusted data.
- No model tools for code execution, arbitrary URLs, private database access or trading.
- Bound prompt/output size, retries, job duration, concurrency and retention.
- Sanitize errors.
- Verify job ownership on every read/cancel request.
- Keep private Supabase schema backend-only.
- Preserve provider/model/input/prompt/schema/validation provenance.
- Forecast output cannot change risk approval or trade plans.
- Deterministic risk engine remains the authority for APPROVED, REJECTED and NEEDS_REVIEW.
- Trade Desk remains manual-only: no broker API, order placement or automated execution.

## 12. Observability

Record secret-free metrics for:

- provider connection state, reconnect count, event lag and stale duration;
- received/rejected/duplicate/out-of-order events;
- candle completeness and REST backfills;
- snapshot age and feature-build duration;
- job queue age and state transitions;
- per-step LLM latency, retries, input/output tokens and cost estimate;
- validation rejection reason;
- forecast completion/failure rate and total horizon duration;
- evaluation metrics by model/prompt/schema version.

Health endpoints must not trigger model calls. Distinguish missing configuration, provider unavailable, LLM unavailable, budget exhausted and model request failure. Define retention for raw buffers, snapshots, responses, forecasts and evaluations.

## 13. Testing plan

### Unit tests

- Binance/Twelve Data event normalization;
- timestamp/timezone and interval boundaries;
- duplicate, stale, out-of-order and gap detection;
- OHLCV aggregation invariants;
- feature calculations without look-ahead;
- context serialization and token/payload limits;
- strict response parsing;
- sequential prompt construction and prior-step inclusion;
- OHLC/volume/timestamp validation;
- job transitions, idempotency, cancellation and retries;
- token/cost budget enforcement;
- sanitized errors.

### Integration tests

- mocked provider streams and disconnect/reconnect/backfill;
- authenticated job create/status/result;
- mocked LLM valid, malformed, delayed, rate-limited and numerically invalid responses;
- loop stops at horizon and appends only validated steps;
- Render restart/recovery behaviour;
- Supabase persistence and duplicate request handling;
- PWA refresh/recovery and separate historical/predicted series.

### Evaluation tests

- deterministic walk-forward fixtures;
- no future-candle leakage;
- baseline comparisons;
- reproducibility where provider determinism permits;
- latency/token/cost measurement at maximum supported horizon.

CI must use mocks by default. A real-provider smoke test is separately gated and requires explicit secrets and approved budget.

## 14. Milestones (one PR at a time)

### M0 — Design and provider/API preflight (this document)

- Inspect existing forecast routes, provider adapters, chart contract, migrations and auth.
- Verify Twelve Data streaming entitlement, symbols, limits and current schema.
- Verify Binance stream schema and reconnect requirements.
- Verify LLM API model ID, structured outputs, context limits, rate limits and current pricing.
- Agree maximum cost per forecast and daily budget.
- Determine whether Render can safely host stream coordinator and sequential job runner, including restart behaviour.

**Exit:** documented provider/model choices, account entitlements and cost budget. No production code or live paid calls.

### M1 — Deterministic market event pipeline

- Add normalized event schemas and provider adapters.
- Add lifecycle-managed stream coordinator, bounded queues, reconnect, health and stale-data detection.
- Add candle aggregation and REST backfill.
- Add deterministic feature encoder and immutable snapshot builder.
- Keep LLM disabled.

**Exit:** tests prove correct timestamped candles/features from fixtures and mocked events, including gaps and reconnects.

### M2 — LLM adapter and single-step proof

- Add server-side provider adapter/configuration.
- Add strict prompt/schema versioning.
- Add one-step request and output validator.
- Add mocks and manually gated real-provider smoke test.
- Measure tokens, latency and cost for one step.

**Exit:** one validated next-interval output from a real approved API call using a fixed fixture; no multi-step jobs or production UI.

### M3 — Sequential orchestrator and persistence

- Add sequential loop with immutable observed history and prior predicted-step context.
- Add forward-only job/step migration and repository.
- Add idempotency, bounded retries, timeouts, cancellation and transitions.
- Add token/cost/concurrency limits and observability.

**Exit:** mocked integration tests prove full multi-step flow and failure/restart handling; gated real run completes a horizon within approved limits.

### M4 — Authenticated API and PWA

- Add authenticated job create/status/result endpoints.
- Add bounded polling and recovery after refresh.
- Add progress/error/partial states and duplicate-submit protection.
- Render predictions separately from observed candles.
- Keep feature disabled by default until release gates pass.

**Exit:** staging end-to-end works without secrets exposure or regression to existing terminal features.

### M5 — Historical evaluation and shadow validation

- Implement walk-forward evaluation harness.
- Compare with baselines across instruments, timeframes and regimes.
- Measure errors by forecast horizon.
- Measure latency, completion rate and real API cost.
- Document failure cases and value over baselines.

**Exit:** reproducible evaluation report and user-approved cost/quality decision.

### M6 — Controlled production enablement

- Enable behind server-side feature flag, default off until approved.
- Start with explicit user-triggered requests, conservative horizon and strict daily limits.
- Monitor provider health, usage, errors and evaluation.
- Provide immediate kill switch and preserve non-forecast terminal operation.
- Expand only after measured stability.

**Exit:** stable operation within approved budget, with provenance and evaluation monitoring.

Each milestone gets its own feature branch and PR. The repository owner reviews and merges; do not auto-merge.

## 15. Rollback

- Feature flag KRONOS_LLM_ENABLED (or final agreed name) defaults false.
- LLM unavailable/budget exhausted: return forecast unavailable.
- Stale provider stream: do not forecast from stale data.
- Partial sequential chain: persist incomplete/failed; do not label complete.
- If stream coordinator fails, existing REST market-data path remains available.
- Disabling the new feature must not affect charts, market data, Gemini, risk engine, journal, sessions or monitoring.
- Never fabricate forecasts or silently invoke local PyTorch as fallback.
- Roll back only new feature code/migration paths; preserve existing user records.

## 16. Open decisions before implementation

1. Does the current Twelve Data plan support WebSocket streaming for target asset classes/symbols? If not, what REST fallback cadence is acceptable?
2. Which exact LLM API provider/model ID is available, supports structured outputs and fits the approved budget?
3. Which initial instruments/timeframes are in scope?
4. Start with a short horizon (e.g. 3–5 steps) until cost/latency/quality are measured?
5. Start with one forecast path; multiple scenarios multiply calls and cost?
6. Is current Render process/job handling durable enough, or is a managed queue needed? No additional paid service without explicit approval.
7. Preserve Kronos-mini as an optional benchmark, disable it, or remove it in a separate change? Do not combine cleanup with initial LLM implementation.
8. What measurable improvement over simple baselines is required for release?

## 17. Definition of done

Kronos-LLM is ready for controlled production only when:

- cloud-only architecture; no Android inference dependency;
- PWA calls authenticated Render APIs only;
- event ingestion and candle aggregation are timestamp-correct and observable;
- snapshots are immutable, provenance-rich and free of future leakage;
- each LLM call predicts exactly one next interval;
- only validated predictions enter subsequent context;
- final output is finite, schema-valid and OHLC-consistent;
- predictions are stored/displayed separately from actual candles;
- job lifecycle, retries, timeouts, cancellation and restart behaviour are tested;
- secrets remain server-side;
- token usage, latency and cost limits are enforced;
- walk-forward and baseline evaluation is documented;
- forecasts cannot change risk approval or execute trades;
- user explicitly approves provider, model, budget and production enablement.

**Current decision:** use this document as the implementation baseline. M0 preflight must finish before M1. This planning document does not authorize code implementation or live provider/LLM activation.
