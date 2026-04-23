import {
  BacktestJob,
  BacktestCompareResponse,
  BacktestRunResponse,
  MarketDataCollectRequest,
  MarketDataBatchRequest,
  MarketDataBatchResult,
  MarketDataDatasetItem,
  MarketDataDetail,
  MarketDataJob,
  MarketDataOperationResponse,
  MarketDataPreview,
  MarketDataSummary,
  MarketDataUpdateRequest,
  RecentBacktestItem,
  SignalResponse,
  StrategyDetail,
  StrategyMeta,
  StrategyParamsResponse,
  WalkforwardCompareResponse,
  WalkforwardBatchRunRequest,
  WalkforwardBatchRunResponse,
  WalkforwardJob,
  WalkforwardListItem,
  WalkforwardRunRequest,
  WalkforwardRunResponse,
  SweepJob,
  SweepListItem,
  SweepRunRequest,
  SweepRunResponse,
  SweepCombinationResult,
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  listStrategies: () => request<StrategyMeta[]>("/strategies"),
  getStrategy: (strategyId: string) => request<StrategyDetail>(`/strategies/${strategyId}`),
  getStrategyParams: (strategyId: string) =>
    request<StrategyParamsResponse>(`/strategies/${strategyId}/params`),
  updateStrategyParams: (strategyId: string, params: Record<string, number>) =>
    request<StrategyParamsResponse>(`/strategies/${strategyId}/params`, {
      method: "PUT",
      body: JSON.stringify({ params }),
    }),
  listSymbols: () => request<{ symbols: string[] }>("/symbols"),
  runBacktest: (payload: {
    strategy_id: string;
    symbol: string;
    timeframe: string;
    timeframe_mapping?: Record<string, string>;
    start_date: string;
    end_date: string;
    params?: Record<string, number>;
    fee_rate?: number;
    entry_fee_rate?: number;
    exit_fee_rate?: number;
    apply_fee_on_entry?: boolean;
    apply_fee_on_exit?: boolean;
    slippage_rate?: number;
    entry_slippage_rate?: number;
    exit_slippage_rate?: number;
    execution_policy?: "next_open" | "signal_close";
    benchmark_enabled?: boolean;
  }) =>
    request<BacktestRunResponse>("/backtests/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createBacktestJob: (payload: {
    strategy_id: string;
    symbol: string;
    timeframe: string;
    timeframe_mapping?: Record<string, string>;
    start_date: string;
    end_date: string;
    params?: Record<string, number>;
    fee_rate?: number;
    entry_fee_rate?: number;
    exit_fee_rate?: number;
    apply_fee_on_entry?: boolean;
    apply_fee_on_exit?: boolean;
    slippage_rate?: number;
    entry_slippage_rate?: number;
    exit_slippage_rate?: number;
    execution_policy?: "next_open" | "signal_close";
    benchmark_enabled?: boolean;
  }) =>
    request<BacktestJob>("/backtests/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getBacktestJob: (jobId: string) => request<BacktestJob>(`/backtests/jobs/${encodeURIComponent(jobId)}`),
  listBacktestJobs: async (limit = 20) => {
    const result = await request<{ items: BacktestJob[] }>(`/backtests/jobs?limit=${limit}`);
    return result.items;
  },
  listBacktestJobsFiltered: async (limit = 20, status?: string, jobType = "backtest") => {
    const q = new URLSearchParams({ limit: String(limit), job_type: jobType });
    if (status) q.set("status", status);
    const result = await request<{ items: BacktestJob[] }>(`/backtests/jobs?${q.toString()}`);
    return result.items;
  },
  cancelBacktestJob: (jobId: string) =>
    request<BacktestJob>(`/backtests/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
    }),
  retryBacktestJob: (jobId: string) =>
    request<BacktestJob>(`/backtests/jobs/${encodeURIComponent(jobId)}/retry`, {
      method: "POST",
    }),
  listRecentBacktests: async () => {
    const result = await request<{ items: RecentBacktestItem[] }>("/backtests/recent?limit=1");
    return result.items;
  },
  listBacktestHistory: async (limit = 20) => {
    const result = await request<{ items: RecentBacktestItem[] }>(`/backtests/recent?limit=${limit}`);
    return result.items;
  },
  compareBacktests: (runIds: string[]) => {
    const qs = runIds.map((id) => `run_ids=${encodeURIComponent(id)}`).join("&");
    return request<BacktestCompareResponse>(`/backtests/compare?${qs}`);
  },
  rerunBacktest: (runId: string) =>
    request<BacktestRunResponse>(`/backtests/rerun/${encodeURIComponent(runId)}`, {
      method: "POST",
    }),
  getBacktestDetail: (runId: string) =>
    request<BacktestRunResponse>(`/backtests/${encodeURIComponent(runId)}`),
  getSignals: (symbol: string, strategyId: string, timeframe = "1d") =>
    request<SignalResponse>(
      `/signals/${encodeURIComponent(symbol)}?strategy_id=${encodeURIComponent(strategyId)}&timeframe=${encodeURIComponent(timeframe)}`,
    ),
  runWalkforward: (payload: WalkforwardRunRequest) =>
    request<WalkforwardRunResponse>("/walkforward/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createWalkforwardJob: (payload: WalkforwardRunRequest) =>
    request<WalkforwardJob>("/walkforward/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getWalkforwardJob: (jobId: string) =>
    request<WalkforwardJob>(`/walkforward/jobs/${encodeURIComponent(jobId)}`),
  listWalkforwardJobs: async (limit = 20, status?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (status) q.set("status", status);
    const result = await request<{ items: WalkforwardJob[] }>(`/walkforward/jobs?${q.toString()}`);
    return result.items;
  },
  cancelWalkforwardJob: (jobId: string) =>
    request<WalkforwardJob>(`/walkforward/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
    }),
  retryWalkforwardJob: (jobId: string) =>
    request<WalkforwardJob>(`/walkforward/jobs/${encodeURIComponent(jobId)}/retry`, {
      method: "POST",
    }),
  runSweep: (payload: SweepRunRequest) =>
    request<SweepRunResponse | SweepJob>("/sweeps/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listSweeps: async (limit = 20) => {
    const result = await request<{ items: SweepListItem[] }>(`/sweeps?limit=${limit}`);
    return result.items;
  },
  getSweepDetail: (sweepRunId: string) =>
    request<SweepRunResponse>(`/sweeps/${encodeURIComponent(sweepRunId)}`),
  rerunSweep: (sweepRunId: string) =>
    request<SweepRunResponse>(`/sweeps/rerun/${encodeURIComponent(sweepRunId)}`, {
      method: "POST",
    }),
  getSweepResults: (sweepRunId: string) =>
    request<{ sweep_run_id: string; total: number; items: SweepCombinationResult[] }>(
      `/sweeps/${encodeURIComponent(sweepRunId)}/results`,
    ),
  getSweepTop: (sweepRunId: string, limit = 10, sortBy = "net_return_pct") =>
    request<{ sweep_run_id: string; sort_by: string; items: SweepCombinationResult[] }>(
      `/sweeps/${encodeURIComponent(sweepRunId)}/top?limit=${limit}&sort_by=${encodeURIComponent(sortBy)}`,
    ),
  listSweepJobs: async (limit = 20, status?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (status) q.set("status", status);
    const result = await request<{ items: SweepJob[] }>(`/sweeps/jobs?${q.toString()}`);
    return result.items;
  },
  getSweepJob: (jobId: string) => request<SweepJob>(`/sweeps/jobs/${encodeURIComponent(jobId)}`),
  cancelSweepJob: (jobId: string) =>
    request<SweepJob>(`/sweeps/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }),
  retrySweepJob: (jobId: string) =>
    request<SweepJob>(`/sweeps/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" }),
  listWalkforwardRuns: async (limit = 20) => {
    const result = await request<{ items: WalkforwardListItem[] }>(`/walkforward?limit=${limit}`);
    return result.items;
  },
  rerunWalkforward: (walkforwardRunId: string) =>
    request<WalkforwardRunResponse>(`/walkforward/rerun/${encodeURIComponent(walkforwardRunId)}`, {
      method: "POST",
    }),
  getWalkforwardDetail: (walkforwardRunId: string) =>
    request<WalkforwardRunResponse>(`/walkforward/${encodeURIComponent(walkforwardRunId)}`),
  compareWalkforwardRuns: (walkforwardRunIds: string[]) => {
    const qs = walkforwardRunIds
      .map((id) => `walkforward_run_ids=${encodeURIComponent(id)}`)
      .join("&");
    return request<WalkforwardCompareResponse>(`/walkforward/compare?${qs}`);
  },
  exportWalkforwardCompareCsv: async (walkforwardRunIds: string[]) => {
    const qs = walkforwardRunIds
      .map((id) => `walkforward_run_ids=${encodeURIComponent(id)}`)
      .join("&");
    const response = await fetch(`${API_BASE_URL}/walkforward/compare.csv?${qs}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `API error ${response.status}`);
    }
    return response.text();
  },
  runWalkforwardBatch: (payload: WalkforwardBatchRunRequest) =>
    request<WalkforwardBatchRunResponse>("/walkforward/batch-run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  collectMarketData: (payload: MarketDataCollectRequest) =>
    request<MarketDataOperationResponse>("/market-data/collect", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateMarketData: (payload: MarketDataUpdateRequest) =>
    request<MarketDataOperationResponse>("/market-data/update", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  collectBatchMarketData: (payload: MarketDataBatchRequest) =>
    request<MarketDataBatchResult>("/market-data/collect-batch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateBatchMarketData: (payload: MarketDataBatchRequest) =>
    request<MarketDataBatchResult>("/market-data/update-batch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listMarketDatasets: async (filters?: {
    source?: string;
    symbol?: string;
    timeframe?: string;
    quality_status?: string;
  }) => {
    const q = new URLSearchParams();
    if (filters?.source) q.set("source", filters.source);
    if (filters?.symbol) q.set("symbol", filters.symbol);
    if (filters?.timeframe) q.set("timeframe", filters.timeframe);
    if (filters?.quality_status) q.set("quality_status", filters.quality_status);
    const result = await request<{ items: MarketDataDatasetItem[] }>(
      `/market-data${q.toString() ? `?${q.toString()}` : ""}`,
    );
    return result.items;
  },
  getMarketDataSummary: (source?: string) =>
    request<MarketDataSummary>(
      `/market-data/summary${source ? `?source=${encodeURIComponent(source)}` : ""}`,
    ),
  listMarketDataBySymbol: async (symbol: string, source?: string) => {
    const q = source ? `?source=${encodeURIComponent(source)}` : "";
    const result = await request<{ items: MarketDataDatasetItem[] }>(
      `/market-data/by-symbol/${encodeURIComponent(symbol)}${q}`,
    );
    return result.items;
  },
  getMarketDataset: (datasetId: string) =>
    request<MarketDataDetail>(`/market-data/${encodeURIComponent(datasetId)}`),
  validateMarketDataset: (datasetId: string, useJob = false) =>
    request<MarketDataOperationResponse>(`/market-data/${encodeURIComponent(datasetId)}/validate`, {
      method: "POST",
      body: JSON.stringify({ use_job: useJob }),
    }),
  previewMarketDataset: (datasetId: string, limit = 20, tail = true) =>
    request<MarketDataPreview>(
      `/market-data/${encodeURIComponent(datasetId)}/preview?limit=${limit}&tail=${tail ? "true" : "false"}`,
    ),
  listMarketDataJobs: async (limit = 20, status?: string, jobType?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (status) q.set("status", status);
    if (jobType) q.set("job_type", jobType);
    const result = await request<{ items: MarketDataJob[] }>(`/market-data/jobs?${q.toString()}`);
    return result.items;
  },
  getMarketDataJob: (jobId: string) =>
    request<MarketDataJob>(`/market-data/jobs/${encodeURIComponent(jobId)}`),
  cancelMarketDataJob: (jobId: string) =>
    request<MarketDataJob>(`/market-data/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
    }),
  retryMarketDataJob: (jobId: string) =>
    request<MarketDataJob>(`/market-data/jobs/${encodeURIComponent(jobId)}/retry`, {
      method: "POST",
    }),
};
