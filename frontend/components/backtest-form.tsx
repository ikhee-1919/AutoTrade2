"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { BacktestRunResponse, StrategyMeta } from "@/types/api";

type BacktestFormProps = {
  strategies: StrategyMeta[];
  symbols: string[];
  onResult: (result: BacktestRunResponse) => void;
};

export function BacktestForm({ strategies, symbols, onResult }: BacktestFormProps) {
  const [strategyId, setStrategyId] = useState(strategies[0]?.strategy_id ?? "");
  const [symbol, setSymbol] = useState(symbols[0] ?? "");
  const [timeframe, setTimeframe] = useState("1d");
  const [trendTimeframe, setTrendTimeframe] = useState("60m");
  const [setupTimeframe, setSetupTimeframe] = useState("15m");
  const [entryTimeframe, setEntryTimeframe] = useState("5m");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<number>(0);
  const [feeRate, setFeeRate] = useState(0.0005);
  const [slippageRate, setSlippageRate] = useState(0.0003);
  const [executionPolicy, setExecutionPolicy] = useState<"next_open" | "signal_close">(
    "next_open",
  );
  const [benchmarkEnabled, setBenchmarkEnabled] = useState(true);

  const canRun = useMemo(
    () => Boolean(strategyId && symbol && startDate && endDate),
    [strategyId, symbol, startDate, endDate],
  );
  const selectedStrategy = useMemo(
    () => strategies.find((s) => s.strategy_id === strategyId),
    [strategies, strategyId],
  );
  const isMtf = selectedStrategy?.mode === "multi_timeframe";
  const tfOptions = ["1m", "5m", "15m", "30m", "60m", "240m", "1d"];

  const run = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setJobStatus("queued");
    setJobProgress(0);
    try {
      const job = await api.createBacktestJob({
        strategy_id: strategyId,
        symbol,
        timeframe: isMtf ? entryTimeframe : timeframe,
        timeframe_mapping: isMtf
          ? {
              trend: trendTimeframe,
              setup: setupTimeframe,
              entry: entryTimeframe,
            }
          : undefined,
        start_date: startDate,
        end_date: endDate,
        fee_rate: feeRate,
        slippage_rate: slippageRate,
        execution_policy: executionPolicy,
        benchmark_enabled: benchmarkEnabled,
      });

      // Poll asynchronous job status until completion.
      for (let i = 0; i < 240; i += 1) {
        const current = await api.getBacktestJob(job.job_id);
        setJobStatus(current.status);
        setJobProgress(current.progress ?? 0);

        if (current.status === "completed" && current.related_run_id) {
          const result = await api.getBacktestDetail(current.related_run_id);
          onResult(result);
          setJobStatus("completed");
          setJobProgress(100);
          return;
        }
        if (current.status === "failed") {
          throw new Error(current.error_summary ?? "Backtest job failed");
        }
        if (current.status === "cancelled") {
          throw new Error("Backtest job was cancelled.");
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }

      throw new Error("Backtest job timed out. Please try again.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid two">
      <div>
        <label>전략</label>
        <select value={strategyId} onChange={(e) => setStrategyId(e.target.value)}>
          {strategies.map((s) => (
            <option key={s.strategy_id} value={s.strategy_id}>
              {s.name} ({s.version})
            </option>
          ))}
        </select>
      </div>
      <div>
        <label>종목</label>
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          {symbols.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label>기본 타임프레임</label>
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} disabled={isMtf}>
          {tfOptions.map((tf) => (
            <option key={tf} value={tf}>
              {tf}
            </option>
          ))}
        </select>
      </div>
      {isMtf ? (
        <>
          <div>
            <label>trend timeframe</label>
            <select value={trendTimeframe} onChange={(e) => setTrendTimeframe(e.target.value)}>
              {tfOptions.map((tf) => (
                <option key={`trend-${tf}`} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>setup timeframe</label>
            <select value={setupTimeframe} onChange={(e) => setSetupTimeframe(e.target.value)}>
              {tfOptions.map((tf) => (
                <option key={`setup-${tf}`} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>entry timeframe</label>
            <select value={entryTimeframe} onChange={(e) => setEntryTimeframe(e.target.value)}>
              {tfOptions.map((tf) => (
                <option key={`entry-${tf}`} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </div>
        </>
      ) : null}
      <div>
        <label>시작일</label>
        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
      </div>
      <div>
        <label>종료일</label>
        <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
      </div>
      <div>
        <label>수수료율 (fee_rate)</label>
        <input
          type="number"
          step="0.0001"
          value={feeRate}
          onChange={(e) => setFeeRate(Number(e.target.value))}
        />
      </div>
      <div>
        <label>슬리피지율 (slippage_rate)</label>
        <input
          type="number"
          step="0.0001"
          value={slippageRate}
          onChange={(e) => setSlippageRate(Number(e.target.value))}
        />
      </div>
      <div>
        <label>체결 정책 (execution_policy)</label>
        <select
          value={executionPolicy}
          onChange={(e) => setExecutionPolicy(e.target.value as "next_open" | "signal_close")}
        >
          <option value="next_open">next_open (보수적)</option>
          <option value="signal_close">signal_close</option>
        </select>
      </div>
      <div>
        <label>Benchmark 사용</label>
        <select
          value={benchmarkEnabled ? "on" : "off"}
          onChange={(e) => setBenchmarkEnabled(e.target.value === "on")}
        >
          <option value="on">on</option>
          <option value="off">off</option>
        </select>
      </div>
      <div style={{ gridColumn: "1 / -1" }}>
        <button type="button" onClick={run} disabled={!canRun || loading}>
          {loading ? "백테스트 작업 실행 중..." : "백테스트 실행"}
        </button>
        {jobStatus ? (
          <p className="small">
            작업 상태: {jobStatus} ({jobProgress.toFixed(0)}%)
          </p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </div>
    </div>
  );
}
