"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { BacktestComparePanel } from "@/components/backtest-compare-panel";
import { BacktestForm } from "@/components/backtest-form";
import { BacktestResult } from "@/components/backtest-result";
import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import { BacktestJob, BacktestRunResponse, RecentBacktestItem, StrategyMeta } from "@/types/api";

export default function BacktestsPage() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [result, setResult] = useState<BacktestRunResponse | null>(null);
  const [history, setHistory] = useState<RecentBacktestItem[]>([]);
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [jobFilter, setJobFilter] = useState<string>("all");

  const refreshHistory = async () => {
    try {
      const items = await api.listBacktestHistory(20);
      setHistory(items);
    } catch {
      setHistory([]);
    }
  };

  const refreshJobs = async () => {
    try {
      const items =
        jobFilter === "all"
          ? await api.listBacktestJobs(20)
          : await api.listBacktestJobsFiltered(20, jobFilter);
      setJobs(items);
    } catch {
      setJobs([]);
    }
  };

  useEffect(() => {
    async function bootstrap() {
      try {
        const [strategyData, symbolData, historyData, jobData] = await Promise.all([
          api.listStrategies(),
          api.listSymbols(),
          api.listBacktestHistory(20),
          api.listBacktestJobs(10),
        ]);
        setStrategies(strategyData);
        setSymbols(symbolData.symbols);
        setHistory(historyData);
        setJobs(jobData);
      } catch {
        setStrategies([]);
        setSymbols([]);
        setHistory([]);
        setJobs([]);
      }
    }
    bootstrap();
  }, []);

  useEffect(() => {
    void refreshJobs();
  }, [jobFilter]);

  const cancelJob = async (jobId: string) => {
    await api.cancelBacktestJob(jobId);
    await refreshJobs();
  };

  const retryJob = async (jobId: string) => {
    await api.retryBacktestJob(jobId);
    await refreshJobs();
  };

  return (
    <div>
      <h1>백테스트 실행</h1>
      <SectionCard title="실행 조건" description="전략/종목/기간을 선택해 백테스트를 실행합니다.">
        {strategies.length > 0 && symbols.length > 0 ? (
          <BacktestForm
            strategies={strategies}
            symbols={symbols}
            onResult={(data) => {
              setResult(data);
              void refreshHistory();
              void refreshJobs();
            }}
          />
        ) : (
          <div className="placeholder">백엔드 연결 후 전략/종목 목록을 불러옵니다.</div>
        )}
      </SectionCard>

      <SectionCard title="실행 결과" description="요약 지표, 거래 로그, 진입/거절 통계">
        <BacktestResult result={result} />
      </SectionCard>

      <SectionCard
        title="백테스트 이력 비교"
        description="최근 실행 이력을 2개 이상 선택해 성과 지표를 비교합니다."
      >
        <BacktestComparePanel
          history={history}
          onRefresh={refreshHistory}
          onRerunComplete={(data) => {
            setResult(data);
          }}
        />
      </SectionCard>

      <SectionCard title="백테스트 작업 이력" description="최근 비동기 작업의 성공/실패 상태">
        <div style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "center" }}>
          <select value={jobFilter} onChange={(e) => setJobFilter(e.target.value)} style={{ width: 180 }}>
            <option value="all">전체 상태</option>
            <option value="queued">queued</option>
            <option value="running">running</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
          </select>
          <button type="button" onClick={() => void refreshJobs()}>
            작업 이력 새로고침
          </button>
        </div>
        {jobs.length === 0 ? (
          <div className="placeholder">아직 작업 이력이 없습니다.</div>
        ) : (
          <div className="grid two">
            {jobs.map((job) => (
              <div key={job.job_id} className="card">
                <div className="small">{new Date(job.created_at).toLocaleString()}</div>
                <p>
                  <strong>{job.request.strategy_id}</strong> / {job.request.symbol}
                </p>
                <p className="small">job_id: {job.job_id.slice(0, 8)}</p>
                <p>
                  상태:{" "}
                  <span className="badge" style={{ background: "#eef4ff", color: "#1d4ed8" }}>
                    {job.status}
                  </span>
                </p>
                <div className="progress-wrap">
                  <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, job.progress ?? 0))}%` }} />
                </div>
                <p className="small">진행률: {(job.progress ?? 0).toFixed(0)}%</p>
                {job.duration_seconds != null ? <p className="small">duration: {job.duration_seconds}s</p> : null}
                {job.related_run_id ? (
                  <p className="small">
                    run: <Link href={`/backtests/${job.related_run_id}`}>{job.related_run_id.slice(0, 8)}</Link>
                  </p>
                ) : null}
                {job.status === "failed" ? <p className="error">{job.error_summary}</p> : null}
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
