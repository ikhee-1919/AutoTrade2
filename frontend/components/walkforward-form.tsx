"use client";

import { useMemo, useState } from "react";
import { useEffect } from "react";

import { api } from "@/lib/api";
import { StrategyDetail, StrategyMeta, WalkforwardRunResponse } from "@/types/api";

type WalkforwardFormProps = {
  strategies: StrategyMeta[];
  symbols: string[];
  onComplete: (result: WalkforwardRunResponse) => void;
};

export function WalkforwardForm({ strategies, symbols, onComplete }: WalkforwardFormProps) {
  const [strategyId, setStrategyId] = useState(strategies[0]?.strategy_id ?? "");
  const [symbol, setSymbol] = useState(symbols[0] ?? "");
  const [timeframe, setTimeframe] = useState("1d");
  const [trendTimeframe, setTrendTimeframe] = useState("60m");
  const [setupTimeframe, setSetupTimeframe] = useState("15m");
  const [entryTimeframe, setEntryTimeframe] = useState("5m");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [trainWindow, setTrainWindow] = useState(60);
  const [testWindow, setTestWindow] = useState(30);
  const [stepSize, setStepSize] = useState(30);
  const [windowUnit, setWindowUnit] = useState<"candles" | "days">("candles");
  const [walkforwardMode, setWalkforwardMode] = useState<"rolling" | "anchored">("rolling");
  const [feeRate, setFeeRate] = useState(0.0005);
  const [slippageRate, setSlippageRate] = useState(0.0003);
  const [executionPolicy, setExecutionPolicy] = useState<"next_open" | "signal_close">(
    "next_open",
  );
  const [benchmarkEnabled, setBenchmarkEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [strategyDetail, setStrategyDetail] = useState<StrategyDetail | null>(null);

  const canRun = useMemo(
    () =>
      Boolean(strategyId && symbol && startDate && endDate) &&
      trainWindow > 0 &&
      testWindow > 0 &&
      stepSize > 0,
    [strategyId, symbol, startDate, endDate, trainWindow, testWindow, stepSize],
  );
  const selectedStrategy = useMemo(
    () => strategies.find((s) => s.strategy_id === strategyId),
    [strategies, strategyId],
  );
  const isMtf = (strategyDetail?.mode ?? selectedStrategy?.mode) === "multi_timeframe";
  const tfOptions = ["1m", "5m", "15m", "30m", "60m", "240m", "1d"];

  useEffect(() => {
    async function loadStrategyDetail() {
      if (!strategyId) return;
      try {
        const detail = await api.getStrategy(strategyId);
        setStrategyDetail(detail);
        const mapping = detail.default_timeframe_mapping ?? {};
        if (mapping.trend) setTrendTimeframe(mapping.trend);
        if (mapping.setup) setSetupTimeframe(mapping.setup);
        if (mapping.entry) setEntryTimeframe(mapping.entry);
        if (mapping.entry && !detail.mode?.includes("multi")) {
          setTimeframe(mapping.entry);
        }
      } catch {
        setStrategyDetail(null);
      }
    }
    void loadStrategyDetail();
  }, [strategyId]);

  const run = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setProgress(0);
    setJobStatus("queued");

    try {
      const job = await api.createWalkforwardJob({
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
        train_window_size: trainWindow,
        test_window_size: testWindow,
        step_size: stepSize,
        window_unit: windowUnit,
        walkforward_mode: walkforwardMode,
        fee_rate: feeRate,
        slippage_rate: slippageRate,
        execution_policy: executionPolicy,
        benchmark_enabled: benchmarkEnabled,
      });

      for (let i = 0; i < 300; i += 1) {
        const current = await api.getWalkforwardJob(job.job_id);
        setJobStatus(current.status);
        setProgress(current.progress ?? 0);
        if (current.status === "completed" && current.related_walkforward_run_id) {
          const result = await api.getWalkforwardDetail(current.related_walkforward_run_id);
          onComplete(result);
          return;
        }
        if (current.status === "failed") {
          throw new Error(current.error_summary ?? "Walk-forward job failed");
        }
        if (current.status === "cancelled") {
          throw new Error("Walk-forward job was cancelled.");
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      throw new Error("Walk-forward job timed out. Please try again.");
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
        {strategyDetail?.required_roles?.length ? (
          <p className="small">
            required roles: {strategyDetail.required_roles.join(", ")} / default mapping:{" "}
            {Object.entries(strategyDetail.default_timeframe_mapping ?? {})
              .map(([role, tf]) => `${role}:${tf}`)
              .join(", ")}
          </p>
        ) : null}
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
                <option key={`wf-trend-${tf}`} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>setup timeframe</label>
            <select value={setupTimeframe} onChange={(e) => setSetupTimeframe(e.target.value)}>
              {tfOptions.map((tf) => (
                <option key={`wf-setup-${tf}`} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>entry timeframe</label>
            <select value={entryTimeframe} onChange={(e) => setEntryTimeframe(e.target.value)}>
              {tfOptions.map((tf) => (
                <option key={`wf-entry-${tf}`} value={tf}>
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
        <label>Train Window</label>
        <input type="number" value={trainWindow} onChange={(e) => setTrainWindow(Number(e.target.value))} />
      </div>
      <div>
        <label>Test Window</label>
        <input type="number" value={testWindow} onChange={(e) => setTestWindow(Number(e.target.value))} />
      </div>
      <div>
        <label>Step Size</label>
        <input type="number" value={stepSize} onChange={(e) => setStepSize(Number(e.target.value))} />
      </div>
      <div>
        <label>Window Unit</label>
        <select value={windowUnit} onChange={(e) => setWindowUnit(e.target.value as "candles" | "days")}>
          <option value="candles">candles</option>
          <option value="days">days</option>
        </select>
      </div>
      <div>
        <label>Walk-Forward Mode</label>
        <select
          value={walkforwardMode}
          onChange={(e) => setWalkforwardMode(e.target.value as "rolling" | "anchored")}
        >
          <option value="rolling">rolling</option>
          <option value="anchored">anchored</option>
        </select>
      </div>
      <div>
        <label>수수료율</label>
        <input type="number" step="0.0001" value={feeRate} onChange={(e) => setFeeRate(Number(e.target.value))} />
      </div>
      <div>
        <label>슬리피지율</label>
        <input type="number" step="0.0001" value={slippageRate} onChange={(e) => setSlippageRate(Number(e.target.value))} />
      </div>
      <div>
        <label>체결 정책</label>
        <select
          value={executionPolicy}
          onChange={(e) => setExecutionPolicy(e.target.value as "next_open" | "signal_close")}
        >
          <option value="next_open">next_open</option>
          <option value="signal_close">signal_close</option>
        </select>
      </div>
      <div>
        <label>Benchmark</label>
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
          {loading ? "Walk-forward 실행 중..." : "Walk-forward 실행"}
        </button>
        {jobStatus ? (
          <p className="small">
            작업 상태: {jobStatus} ({progress.toFixed(0)}%)
          </p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </div>
    </div>
  );
}
