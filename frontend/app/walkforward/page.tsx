"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { WalkforwardForm } from "@/components/walkforward-form";
import { WalkforwardResult } from "@/components/walkforward-result";
import { api } from "@/lib/api";
import { StrategyMeta, WalkforwardJob, WalkforwardListItem, WalkforwardRunResponse } from "@/types/api";

export default function WalkforwardPage() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [result, setResult] = useState<WalkforwardRunResponse | null>(null);
  const [runs, setRuns] = useState<WalkforwardListItem[]>([]);
  const [jobs, setJobs] = useState<WalkforwardJob[]>([]);
  const [jobFilter, setJobFilter] = useState<string>("all");
  const [batchStrategyId, setBatchStrategyId] = useState("");
  const [batchSymbols, setBatchSymbols] = useState<string[]>([]);
  const [batchModes, setBatchModes] = useState<("rolling" | "anchored")[]>(["rolling"]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchMessage, setBatchMessage] = useState<string | null>(null);

  const refreshRuns = async () => {
    try {
      const items = await api.listWalkforwardRuns(20);
      setRuns(items);
    } catch {
      setRuns([]);
    }
  };

  const refreshJobs = async () => {
    try {
      const items = await api.listWalkforwardJobs(20, jobFilter === "all" ? undefined : jobFilter);
      setJobs(items);
    } catch {
      setJobs([]);
    }
  };

  useEffect(() => {
    async function bootstrap() {
      try {
        const [strategyData, symbolData, runData, jobData] = await Promise.all([
          api.listStrategies(),
          api.listSymbols(),
          api.listWalkforwardRuns(20),
          api.listWalkforwardJobs(20),
        ]);
        setStrategies(strategyData);
        setSymbols(symbolData.symbols);
        setBatchStrategyId(strategyData[0]?.strategy_id ?? "");
        setBatchSymbols(symbolData.symbols.slice(0, 2));
        setRuns(runData);
        setJobs(jobData);
      } catch {
        setStrategies([]);
        setSymbols([]);
        setRuns([]);
        setJobs([]);
      }
    }
    void bootstrap();
  }, []);

  useEffect(() => {
    void refreshJobs();
  }, [jobFilter]);

  const cancelJob = async (jobId: string) => {
    await api.cancelWalkforwardJob(jobId);
    await refreshJobs();
  };

  const retryJob = async (jobId: string) => {
    await api.retryWalkforwardJob(jobId);
    await refreshJobs();
  };

  const toggleBatchSymbol = (symbol: string) => {
    setBatchSymbols((prev) =>
      prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol],
    );
  };

  const toggleBatchMode = (mode: "rolling" | "anchored") => {
    setBatchModes((prev) => (prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode]));
  };

  const runBatch = async () => {
    if (!batchStrategyId || batchSymbols.length === 0 || batchModes.length === 0) return;
    setBatchLoading(true);
    setBatchMessage(null);
    try {
      const batch = await api.runWalkforwardBatch({
        strategy_id: batchStrategyId,
        symbols: batchSymbols,
        timeframe: "1d",
        start_date: "2025-01-01",
        end_date: "2025-12-31",
        train_window_size: 60,
        test_window_size: 30,
        step_size: 30,
        window_unit: "candles",
        walkforward_modes: batchModes,
        benchmark_enabled: true,
        use_jobs: true,
      });
      setBatchMessage(`batch ${batch.batch_id.slice(0, 8)} 생성: ${batch.total_requested}개 요청`);
      await refreshJobs();
    } catch (e) {
      setBatchMessage(e instanceof Error ? e.message : "Batch 생성 실패");
    } finally {
      setBatchLoading(false);
    }
  };

  return (
    <div>
      <h1>Walk-Forward 분석</h1>
      <div style={{ marginBottom: 12 }}>
        <Link href="/walkforward/compare">Walk-Forward 비교 화면으로 이동</Link>
      </div>
      <SectionCard title="실행 조건" description="Train/Test/Step 기반 세그먼트 평가를 실행합니다.">
        {strategies.length > 0 && symbols.length > 0 ? (
          <WalkforwardForm
            strategies={strategies}
            symbols={symbols}
            onComplete={(data) => {
              setResult(data);
              void refreshRuns();
              void refreshJobs();
            }}
          />
        ) : (
          <div className="placeholder">전략/종목 데이터를 불러오는 중입니다.</div>
        )}
      </SectionCard>

      <SectionCard title="최근 실행 결과" description="최근 완료된 walk-forward 요약">
        <WalkforwardResult result={result} />
      </SectionCard>

      <SectionCard title="Batch 실행 (골격)" description="여러 symbol/mode 조합을 한 번에 작업 큐에 등록합니다.">
        <div className="grid two">
          <div>
            <label>전략</label>
            <select value={batchStrategyId} onChange={(e) => setBatchStrategyId(e.target.value)}>
              {strategies.map((s) => (
                <option key={s.strategy_id} value={s.strategy_id}>
                  {s.name} ({s.version})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>모드 선택</label>
            <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
              <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={batchModes.includes("rolling")}
                  onChange={() => toggleBatchMode("rolling")}
                  style={{ width: "auto" }}
                />
                rolling
              </label>
              <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={batchModes.includes("anchored")}
                  onChange={() => toggleBatchMode("anchored")}
                  style={{ width: "auto" }}
                />
                anchored
              </label>
            </div>
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <label>심볼 선택</label>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 8 }}>
            {symbols.map((symbol) => (
              <label key={symbol} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={batchSymbols.includes(symbol)}
                  onChange={() => toggleBatchSymbol(symbol)}
                  style={{ width: "auto" }}
                />
                {symbol}
              </label>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 12 }}>
          <button
            type="button"
            onClick={() => void runBatch()}
            disabled={batchLoading || batchSymbols.length === 0 || batchModes.length === 0}
          >
            {batchLoading ? "Batch 생성 중..." : "Batch 실행 등록"}
          </button>
          {batchMessage ? <p className="small">{batchMessage}</p> : null}
        </div>
      </SectionCard>

      <SectionCard title="Walk-Forward 이력" description="세그먼트 기반 성과 이력">
        {runs.length === 0 ? (
          <div className="placeholder">아직 walk-forward 실행 이력이 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>생성시각</th>
                <th>id</th>
                <th>전략/종목</th>
                <th>tf mapping</th>
                <th>요청기간</th>
                <th>mode</th>
                <th>segment</th>
                <th>총 Net</th>
                <th>평균 Segment</th>
                <th>Benchmark 초과</th>
                <th>재실행</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.walkforward_run_id}>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                  <td>
                    <Link href={`/walkforward/${run.walkforward_run_id}`}>
                      {run.walkforward_run_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td>
                    {run.strategy_id} / {run.symbol}
                  </td>
                  <td>
                    {run.timeframe_mapping
                      ? Object.entries(run.timeframe_mapping)
                          .map(([role, tf]) => `${role}:${tf}`)
                          .join(", ")
                      : "-"}
                  </td>
                  <td>
                    {run.requested_period.start_date} ~ {run.requested_period.end_date}
                  </td>
                  <td>{run.walkforward_mode}</td>
                  <td>
                    {run.completed_segment_count}/{run.segment_count}
                  </td>
                  <td>{run.total_net_return_pct.toFixed(2)}%</td>
                  <td>{run.average_segment_return_pct.toFixed(2)}%</td>
                  <td>{run.segments_beating_benchmark}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() =>
                        void api.rerunWalkforward(run.walkforward_run_id).then((data) => {
                          setResult(data);
                          void refreshRuns();
                        })
                      }
                    >
                      rerun
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <SectionCard title="Walk-Forward 작업 이력" description="비동기 작업 상태 및 진행률">
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <select value={jobFilter} onChange={(e) => setJobFilter(e.target.value)} style={{ width: 180 }}>
            <option value="all">전체 상태</option>
            <option value="queued">queued</option>
            <option value="running">running</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
          </select>
          <button type="button" onClick={() => void refreshJobs()}>
            새로고침
          </button>
        </div>
        {jobs.length === 0 ? (
          <div className="placeholder">작업 이력이 없습니다.</div>
        ) : (
          <div className="grid two">
            {jobs.map((job) => (
              <div key={job.job_id} className="card">
                <div className="small">{new Date(job.created_at).toLocaleString()}</div>
                <p className="small">job_id: {job.job_id.slice(0, 8)}</p>
                <p>상태: {job.status}</p>
                <div className="progress-wrap">
                  <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, job.progress ?? 0))}%` }} />
                </div>
                <p className="small">
                  진행률: {(job.progress ?? 0).toFixed(0)}% ({job.segment_completed ?? 0}/{job.segment_total ?? 0})
                </p>
                {job.related_walkforward_run_id ? (
                  <p className="small">
                    run:{" "}
                    <Link href={`/walkforward/${job.related_walkforward_run_id}`}>
                      {job.related_walkforward_run_id.slice(0, 8)}
                    </Link>
                  </p>
                ) : null}
                {job.error_summary ? <p className="error">{job.error_summary}</p> : null}
                <div style={{ display: "flex", gap: 8 }}>
                  {(job.status === "queued" || job.status === "running") && (
                    <button type="button" onClick={() => void cancelJob(job.job_id)}>
                      취소
                    </button>
                  )}
                  {job.status === "failed" && (
                    <button type="button" onClick={() => void retryJob(job.job_id)}>
                      재시도
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
