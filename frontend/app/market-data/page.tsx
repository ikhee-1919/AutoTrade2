"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import { MarketDataBatchResult, MarketDataDatasetItem, MarketDataJob, MarketDataSummary } from "@/types/api";

const DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "60m", "240m", "1d"];
const DEFAULT_SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"];

export default function MarketDataPage() {
  const [datasets, setDatasets] = useState<MarketDataDatasetItem[]>([]);
  const [jobs, setJobs] = useState<MarketDataJob[]>([]);
  const [summary, setSummary] = useState<MarketDataSummary | null>(null);
  const [allSymbols, setAllSymbols] = useState<string[]>(DEFAULT_SYMBOLS);

  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(["KRW-BTC", "KRW-ETH"]);
  const [selectedTimeframes, setSelectedTimeframes] = useState<string[]>(["5m", "60m", "1d"]);
  const [mode, setMode] = useState<"full_collect" | "incremental_update">("full_collect");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [validateAfter, setValidateAfter] = useState(true);
  const [useJob, setUseJob] = useState(true);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<MarketDataBatchResult | null>(null);

  const combinations = useMemo(
    () => selectedSymbols.length * selectedTimeframes.length,
    [selectedSymbols, selectedTimeframes],
  );

  const refreshAll = async () => {
    try {
      const [datasetData, jobData, summaryData, symbolData] = await Promise.all([
        api.listMarketDatasets(),
        api.listMarketDataJobs(30),
        api.getMarketDataSummary(),
        api.listSymbols(),
      ]);
      setDatasets(datasetData);
      setJobs(jobData);
      setSummary(summaryData);
      setAllSymbols(Array.from(new Set([...DEFAULT_SYMBOLS, ...symbolData.symbols])));
    } catch {
      setDatasets([]);
      setJobs([]);
      setSummary(null);
    }
  };

  useEffect(() => {
    void refreshAll();
  }, []);

  const toggleSymbol = (symbol: string) => {
    setSelectedSymbols((prev) =>
      prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol],
    );
  };

  const toggleTimeframe = (timeframe: string) => {
    setSelectedTimeframes((prev) =>
      prev.includes(timeframe) ? prev.filter((t) => t !== timeframe) : [...prev, timeframe],
    );
  };

  const runBatch = async () => {
    if (selectedSymbols.length === 0 || selectedTimeframes.length === 0) return;
    setLoading(true);
    setMessage(null);
    setBatchResult(null);
    try {
      const payload = {
        source: "upbit",
        symbols: selectedSymbols,
        timeframes: selectedTimeframes,
        start_date: mode === "full_collect" ? startDate : null,
        end_date: endDate,
        mode,
        validate_after_collect: validateAfter,
        use_job: useJob,
      };
      const result =
        mode === "full_collect"
          ? await api.collectBatchMarketData(payload)
          : await api.updateBatchMarketData(payload);
      setBatchResult(result);
      if (result.mode === "job") {
        setMessage(`Batch job 등록 완료: ${result.job_id}`);
      } else {
        setMessage(
          `Batch 완료: completed=${result.completed_combinations}, failed=${result.failed_combinations}, skipped=${result.skipped_combinations}`,
        );
      }
      await refreshAll();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Batch 실행 실패");
    } finally {
      setLoading(false);
    }
  };

  const cancelJob = async (jobId: string) => {
    await api.cancelMarketDataJob(jobId);
    await refreshAll();
  };
  const retryJob = async (jobId: string) => {
    await api.retryMarketDataJob(jobId);
    await refreshAll();
  };

  return (
    <div>
      <h1>데이터 관리 (멀티 타임프레임)</h1>

      <SectionCard title="Batch Collect / Update" description="symbols x timeframes 조합 일괄 실행">
        <div className="grid two">
          <div>
            <label>모드</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "full_collect" | "incremental_update")}
            >
              <option value="full_collect">full_collect</option>
              <option value="incremental_update">incremental_update</option>
            </select>
          </div>
          <div>
            <label>조합 수</label>
            <input value={String(combinations)} readOnly />
          </div>
          <div>
            <label>시작일 (full_collect)</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              disabled={mode !== "full_collect"}
            />
          </div>
          <div>
            <label>종료일</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
          <div>
            <label>validate_after_collect</label>
            <select
              value={validateAfter ? "on" : "off"}
              onChange={(e) => setValidateAfter(e.target.value === "on")}
            >
              <option value="on">on</option>
              <option value="off">off</option>
            </select>
          </div>
          <div>
            <label>use_job</label>
            <select value={useJob ? "on" : "off"} onChange={(e) => setUseJob(e.target.value === "on")}>
              <option value="on">on</option>
              <option value="off">off</option>
            </select>
          </div>
        </div>

        <div style={{ marginTop: 10 }}>
          <label>심볼 선택</label>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 8 }}>
            {allSymbols.map((symbol) => (
              <label key={symbol} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input
                  type="checkbox"
                  style={{ width: "auto" }}
                  checked={selectedSymbols.includes(symbol)}
                  onChange={() => toggleSymbol(symbol)}
                />
                {symbol}
              </label>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 10 }}>
          <label>타임프레임 선택</label>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 8 }}>
            {DEFAULT_TIMEFRAMES.map((tf) => (
              <label key={tf} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input
                  type="checkbox"
                  style={{ width: "auto" }}
                  checked={selectedTimeframes.includes(tf)}
                  onChange={() => toggleTimeframe(tf)}
                />
                {tf}
              </label>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <button
            type="button"
            onClick={() => void runBatch()}
            disabled={loading || selectedSymbols.length === 0 || selectedTimeframes.length === 0}
          >
            {loading ? "Batch 실행 중..." : "Batch 실행"}
          </button>
          {message ? <p className="small">{message}</p> : null}
        </div>

        {batchResult ? (
          <div className="grid two" style={{ marginTop: 12 }}>
            <div className="card">
              <div className="small">completed/failed/skipped</div>
              <strong>
                {batchResult.completed_combinations}/{batchResult.failed_combinations}/
                {batchResult.skipped_combinations}
              </strong>
            </div>
            <div className="card">
              <div className="small">quality pass/warning/fail</div>
              <strong>
                {batchResult.pass_count}/{batchResult.warning_count}/{batchResult.fail_count}
              </strong>
            </div>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="데이터 요약" description="symbol/timeframe 가용성과 품질 상태 집계">
        {!summary ? (
          <div className="placeholder">summary 로딩 중...</div>
        ) : (
          <>
            <div className="grid two">
              <div className="card">
                <div className="small">총 datasets</div>
                <strong>{summary.total_datasets}</strong>
              </div>
              <div className="card">
                <div className="small">quality pass/warning/fail</div>
                <strong>
                  {summary.pass_count}/{summary.warning_count}/{summary.fail_count}
                </strong>
              </div>
              <div className="card">
                <div className="small">symbols</div>
                <strong>{summary.available_symbols.join(", ") || "-"}</strong>
              </div>
              <div className="card">
                <div className="small">timeframes</div>
                <strong>{summary.available_timeframes.join(", ") || "-"}</strong>
              </div>
            </div>
            <p className="small">
              latest updated: {summary.latest_updated_at ? new Date(summary.latest_updated_at).toLocaleString() : "-"}
            </p>

            <table>
              <thead>
                <tr>
                  <th>symbol</th>
                  <th>pass</th>
                  <th>warning</th>
                  <th>fail</th>
                  <th>timeframes</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary.by_symbol).map(([symbol, info]) => (
                  <tr key={symbol}>
                    <td>{symbol}</td>
                    <td>{info.pass_count}</td>
                    <td>{info.warning_count}</td>
                    <td>{info.fail_count}</td>
                    <td>
                      {Object.entries(info.timeframes)
                        .map(([tf, v]) => `${tf}:${v.quality_status ?? "-"}`)
                        .join(" | ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </SectionCard>

      <SectionCard title="데이터셋 목록" description="타임프레임별 dataset 상태 확인">
        {datasets.length === 0 ? (
          <div className="placeholder">저장된 데이터셋이 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>source</th>
                <th>symbol</th>
                <th>timeframe</th>
                <th>기간</th>
                <th>rows</th>
                <th>quality</th>
                <th>updated</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.dataset_id}>
                  <td>
                    <Link href={`/market-data/${encodeURIComponent(d.dataset_id)}`}>{d.dataset_id}</Link>
                  </td>
                  <td>{d.source}</td>
                  <td>{d.symbol}</td>
                  <td>{d.timeframe}</td>
                  <td>
                    {d.start_at ?? "-"} ~ {d.end_at ?? "-"}
                  </td>
                  <td>{d.row_count}</td>
                  <td>{d.quality_status}</td>
                  <td>{new Date(d.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <SectionCard title="Batch Job 이력" description="collect/update/validate/batch 상태 추적">
        {jobs.length === 0 ? (
          <div className="placeholder">market data job이 없습니다.</div>
        ) : (
          <div className="grid two">
            {jobs.map((job) => (
              <div key={job.job_id} className="card">
                <p className="small">
                  {job.job_type} / {job.job_id.slice(0, 8)}
                </p>
                <p>상태: {job.status}</p>
                <div className="progress-wrap">
                  <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }} />
                </div>
                {job.total_combinations != null ? (
                  <p className="small">
                    combinations: {job.completed_combinations ?? 0}/{job.total_combinations} (failed{" "}
                    {job.failed_combinations ?? 0})
                  </p>
                ) : null}
                {job.current_symbol || job.current_timeframe ? (
                  <p className="small">
                    current: {job.current_symbol ?? "-"} / {job.current_timeframe ?? "-"}
                  </p>
                ) : null}
                {job.related_dataset_id ? (
                  <p className="small">
                    dataset:{" "}
                    <Link href={`/market-data/${encodeURIComponent(job.related_dataset_id)}`}>
                      {job.related_dataset_id}
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

      <SectionCard title="백테스트/워크포워드 선택 정책" description="timeframe별 validated dataset 우선">
        <p className="small">
          provider는 symbol+timeframe 기준으로 collected dataset(quality fail 제외)을 sample보다 우선 선택합니다.
        </p>
      </SectionCard>
    </div>
  );
}
