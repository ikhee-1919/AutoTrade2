"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import { SweepJob, SweepListItem, StrategyMeta } from "@/types/api";

type ParamRow = { key: string; values: string };

export default function SweepsPage() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [runs, setRuns] = useState<SweepListItem[]>([]);
  const [jobs, setJobs] = useState<SweepJob[]>([]);

  const [strategyId, setStrategyId] = useState("");
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("1d");
  const [trendTf, setTrendTf] = useState("60m");
  const [setupTf, setSetupTf] = useState("15m");
  const [entryTf, setEntryTf] = useState("5m");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [rows, setRows] = useState<ParamRow[]>([
    { key: "score_threshold", values: "0.6,0.7,0.8" },
    { key: "volume_multiplier", values: "1.0,1.2" },
  ]);
  const [useJob, setUseJob] = useState(true);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedStrategy = useMemo(
    () => strategies.find((s) => s.strategy_id === strategyId),
    [strategies, strategyId],
  );
  const isMtf = selectedStrategy?.mode === "multi_timeframe";
  const tfOptions = ["1m", "5m", "15m", "30m", "60m", "240m", "1d"];

  const refresh = async () => {
    try {
      const [s, syms, list, j] = await Promise.all([
        api.listStrategies(),
        api.listSymbols(),
        api.listSweeps(30),
        api.listSweepJobs(20),
      ]);
      setStrategies(s);
      setSymbols(syms.symbols);
      if (!strategyId) setStrategyId(s[0]?.strategy_id ?? "");
      if (!symbol) setSymbol(syms.symbols[0] ?? "");
      setRuns(list);
      setJobs(j);
    } catch {
      setStrategies([]);
      setSymbols([]);
      setRuns([]);
      setJobs([]);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const parseSweepSpace = () => {
    const space: Record<string, Array<number | string>> = {};
    for (const row of rows) {
      const key = row.key.trim();
      if (!key) continue;
      const values = row.values
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean)
        .map((v) => {
          const n = Number(v);
          return Number.isFinite(n) && v !== "" ? n : v;
        });
      if (values.length > 0) {
        space[key] = values;
      }
    }
    return space;
  };

  const runSweep = async () => {
    if (!strategyId || !symbol) return;
    setLoading(true);
    setMessage(null);
    try {
      const payload = {
        strategy_id: strategyId,
        symbol,
        timeframe: isMtf ? entryTf : timeframe,
        timeframe_mapping: isMtf ? { trend: trendTf, setup: setupTf, entry: entryTf } : undefined,
        start_date: startDate,
        end_date: endDate,
        sweep_space: parseSweepSpace(),
        use_job: useJob,
      };
      const res = await api.runSweep(payload);
      if ("job_id" in res) {
        setMessage(`sweep job queued: ${res.job_id}`);
      } else {
        setMessage(`sweep completed: ${res.sweep_run_id}`);
      }
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "sweep 실행 실패");
    } finally {
      setLoading(false);
    }
  };

  const addRow = () => setRows((prev) => [...prev, { key: "", values: "" }]);
  const updateRow = (idx: number, patch: Partial<ParamRow>) =>
    setRows((prev) => prev.map((item, i) => (i === idx ? { ...item, ...patch } : item)));
  const removeRow = (idx: number) => setRows((prev) => prev.filter((_, i) => i !== idx));

  return (
    <div>
      <h1>파라미터 스윕</h1>
      <SectionCard title="Sweep 실행" description="deterministic grid sweep 실행">
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
              {symbols.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>기본 timeframe</label>
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
                <select value={trendTf} onChange={(e) => setTrendTf(e.target.value)}>
                  {tfOptions.map((tf) => (
                    <option key={`trend-${tf}`} value={tf}>
                      {tf}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>setup timeframe</label>
                <select value={setupTf} onChange={(e) => setSetupTf(e.target.value)}>
                  {tfOptions.map((tf) => (
                    <option key={`setup-${tf}`} value={tf}>
                      {tf}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>entry timeframe</label>
                <select value={entryTf} onChange={(e) => setEntryTf(e.target.value)}>
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
            <label>use_job</label>
            <select value={useJob ? "on" : "off"} onChange={(e) => setUseJob(e.target.value === "on")}>
              <option value="on">on</option>
              <option value="off">off</option>
            </select>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <label>sweep_space</label>
          {rows.map((row, idx) => (
            <div key={`row-${idx}`} style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <input
                placeholder="param key"
                value={row.key}
                onChange={(e) => updateRow(idx, { key: e.target.value })}
              />
              <input
                placeholder="comma values (e.g. 0.6,0.7,0.8)"
                value={row.values}
                onChange={(e) => updateRow(idx, { values: e.target.value })}
              />
              <button type="button" onClick={() => removeRow(idx)}>
                삭제
              </button>
            </div>
          ))}
          <div style={{ marginTop: 8 }}>
            <button type="button" onClick={addRow}>
              파라미터 행 추가
            </button>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <button type="button" onClick={() => void runSweep()} disabled={loading}>
            {loading ? "실행 중..." : "Sweep 실행"}
          </button>
          {message ? <p className="small">{message}</p> : null}
        </div>
      </SectionCard>

      <SectionCard title="Sweep 목록" description="최근 sweep 실행">
        {runs.length === 0 ? (
          <div className="placeholder">sweep 실행 이력이 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>created_at</th>
                <th>sweep_id</th>
                <th>전략/종목</th>
                <th>timeframe</th>
                <th>조합</th>
                <th>avg net</th>
                <th>top net</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.sweep_run_id}>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                  <td>
                    <Link href={`/sweeps/${run.sweep_run_id}`}>{run.sweep_run_id.slice(0, 8)}</Link>
                  </td>
                  <td>
                    {run.strategy_id} / {run.symbol}
                  </td>
                  <td>
                    {run.timeframe_mapping
                      ? Object.entries(run.timeframe_mapping)
                          .map(([role, tf]) => `${role}:${tf}`)
                          .join(", ")
                      : run.timeframe}
                  </td>
                  <td>
                    {run.completed_combinations}/{run.total_combinations} (fail {run.failed_combinations})
                  </td>
                  <td>{run.average_net_return.toFixed(2)}%</td>
                  <td>{run.top_net_return_pct.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <SectionCard title="Sweep 작업 이력" description="비동기 실행 상태">
        {jobs.length === 0 ? (
          <div className="placeholder">sweep job 이력이 없습니다.</div>
        ) : (
          <div className="grid two">
            {jobs.map((job) => (
              <div key={job.job_id} className="card">
                <p className="small">{new Date(job.created_at).toLocaleString()}</p>
                <p className="small">job_id: {job.job_id.slice(0, 8)}</p>
                <p>status: {job.status}</p>
                <div className="progress-wrap">
                  <div
                    className="progress-fill"
                    style={{ width: `${Math.max(0, Math.min(100, job.progress ?? 0))}%` }}
                  />
                </div>
                <p className="small">
                  progress: {(job.progress ?? 0).toFixed(0)}% ({job.completed_combinations ?? 0}/
                  {job.total_combinations ?? 0})
                </p>
                {job.related_sweep_run_id ? (
                  <p className="small">
                    run:{" "}
                    <Link href={`/sweeps/${job.related_sweep_run_id}`}>{job.related_sweep_run_id.slice(0, 8)}</Link>
                  </p>
                ) : null}
                {job.error_summary ? <p className="error">{job.error_summary}</p> : null}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
