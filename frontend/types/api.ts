export type StrategyMeta = {
  strategy_id: string;
  name: string;
  version: string;
  description: string;
  mode?: "single_timeframe" | "multi_timeframe" | string;
  required_roles?: string[];
  optional_roles?: string[];
};

export type StrategyDetail = StrategyMeta & {
  default_params: Record<string, number>;
  default_timeframe_mapping?: Record<string, string>;
};

export type StrategyParamsResponse = {
  strategy_id: string;
  params: Record<string, number>;
};

export type BacktestSummary = {
  total_return_pct: number;
  gross_return_pct: number;
  net_return_pct: number;
  trade_count: number;
  win_rate: number;
  max_drawdown: number;
  avg_profit: number;
  avg_loss: number;
  total_fees_paid: number;
  total_slippage_cost: number;
  total_trading_cost: number;
  fee_impact_pct: number;
  slippage_impact_pct: number;
  cost_drag_pct: number;
};

export type BacktestTrade = {
  entry_time: string;
  exit_time: string;
  side: string;
  intended_entry_price: number;
  filled_entry_price: number;
  intended_exit_price: number;
  filled_exit_price: number;
  gross_pnl: number;
  net_pnl: number;
  fee_entry: number;
  fee_exit: number;
  total_fees: number;
  slippage_entry_cost: number;
  slippage_exit_cost: number;
  total_slippage_cost: number;
  total_trading_cost: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  reason: string;
};

export type BacktestRunResponse = {
  run_id: string;
  rerun_of_run_id?: string | null;
  run_at: string;
  strategy_id: string;
  strategy_version: string;
  code_version: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string> | null;
  start_date: string;
  end_date: string;
  params_used: Record<string, number>;
  params_snapshot: Record<string, unknown>;
  params_hash: string;
  data_signature: {
    source: string;
    candle_count: number;
    first_timestamp?: string | null;
    last_timestamp?: string | null;
    candles_hash: string;
    dataset_id?: string | null;
    dataset_signature?: string | null;
  };
  selected_datasets_by_role?: Record<
    string,
    {
      role: string;
      timeframe: string;
      source_type: string;
      dataset_id?: string | null;
      dataset_signature?: string | null;
      quality_status?: string | null;
    }
  >;
  execution_config: {
    execution_policy: "next_open" | "signal_close";
    fee_rate: number;
    entry_fee_rate: number;
    exit_fee_rate: number;
    apply_fee_on_entry: boolean;
    apply_fee_on_exit: boolean;
    slippage_rate: number;
    entry_slippage_rate: number;
    exit_slippage_rate: number;
    benchmark_enabled: boolean;
  };
  run_tag?: string | null;
  note?: string | null;
  summary: BacktestSummary;
  benchmark?: {
    benchmark_buy_and_hold_return_pct: number;
    strategy_excess_return_pct: number;
    benchmark_start_price: number;
    benchmark_end_price: number;
    benchmark_curve: { timestamp: string; equity: number }[];
  } | null;
  trades: BacktestTrade[];
  equity_curve: { timestamp: string; equity: number }[];
  diagnostics: {
    reject_reason_counts: Record<string, number>;
    regime_counts: Record<string, number>;
  };
};

export type RecentBacktestItem = {
  run_id: string;
  rerun_of_run_id?: string | null;
  run_at: string;
  strategy_id: string;
  strategy_version: string;
  code_version: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string> | null;
  start_date: string;
  end_date: string;
  params_used: Record<string, number>;
  params_snapshot: Record<string, unknown>;
  params_hash: string;
  data_signature: {
    source: string;
    candle_count: number;
    first_timestamp?: string | null;
    last_timestamp?: string | null;
    candles_hash: string;
    dataset_id?: string | null;
    dataset_signature?: string | null;
  };
  selected_datasets_by_role?: Record<
    string,
    {
      role: string;
      timeframe: string;
      source_type: string;
      dataset_id?: string | null;
      dataset_signature?: string | null;
      quality_status?: string | null;
    }
  >;
  execution_config: {
    execution_policy: "next_open" | "signal_close";
    fee_rate: number;
    entry_fee_rate: number;
    exit_fee_rate: number;
    apply_fee_on_entry: boolean;
    apply_fee_on_exit: boolean;
    slippage_rate: number;
    entry_slippage_rate: number;
    exit_slippage_rate: number;
    benchmark_enabled: boolean;
  };
  run_tag?: string | null;
  total_return_pct: number;
  gross_return_pct: number;
  net_return_pct: number;
  total_trading_cost: number;
  cost_drag_pct: number;
  benchmark_buy_and_hold_return_pct: number;
  strategy_excess_return_pct: number;
  trade_count: number;
};

export type BacktestCompareItem = {
  run_id: string;
  run_at: string;
  strategy_id: string;
  strategy_version: string;
  code_version: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string> | null;
  timeframe_mapping_summary?: string | null;
  start_date: string;
  end_date: string;
  total_return_pct: number;
  gross_return_pct: number;
  net_return_pct: number;
  max_drawdown: number;
  win_rate: number;
  trade_count: number;
  summary_avg_profit: number;
  summary_avg_loss: number;
  total_fees_paid: number;
  total_slippage_cost: number;
  total_trading_cost: number;
  cost_drag_pct: number;
  benchmark_buy_and_hold_return_pct: number;
  strategy_excess_return_pct: number;
  top_reject_reason?: string | null;
  return_gap_vs_best: number;
  mdd_gap_vs_best: number;
  run_tag?: string | null;
};

export type BacktestCompareResponse = {
  compared_count: number;
  best_run_id: string;
  items: BacktestCompareItem[];
};

export type BacktestJobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export type BacktestJob = {
  job_id: string;
  job_type: string;
  status: BacktestJobStatus;
  progress: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  related_run_id?: string | null;
  error_summary?: string | null;
  error_detail?: string | null;
  retry_count: number;
  parent_job_id?: string | null;
  request_hash: string;
  duplicate_of_job_id?: string | null;
  request: {
    strategy_id: string;
    symbol: string;
    timeframe: string;
    timeframe_mapping?: Record<string, string> | null;
    start_date: string;
    end_date: string;
    params?: Record<string, number> | null;
    fee_rate: number;
    entry_fee_rate?: number | null;
    exit_fee_rate?: number | null;
    apply_fee_on_entry: boolean;
    apply_fee_on_exit: boolean;
    slippage_rate: number;
    entry_slippage_rate?: number | null;
    exit_slippage_rate?: number | null;
    execution_policy: "next_open" | "signal_close";
    benchmark_enabled: boolean;
    run_tag?: string | null;
    note?: string | null;
  };
};

export type SignalItem = {
  timestamp: string;
  price: number;
  regime: string;
  entry_allowed: boolean;
  score: number;
  reject_reason: string | null;
};

export type SignalResponse = {
  symbol: string;
  strategy_id: string;
  timeframe: string;
  prices: { timestamp: string; close: number }[];
  signals: SignalItem[];
};

export type WalkforwardRunRequest = {
  strategy_id: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string>;
  start_date: string;
  end_date: string;
  train_window_size: number;
  test_window_size: number;
  step_size: number;
  window_unit: "candles" | "days";
  walkforward_mode?: "rolling" | "anchored";
  params?: Record<string, number>;
  fee_rate?: number;
  entry_fee_rate?: number | null;
  exit_fee_rate?: number | null;
  apply_fee_on_entry?: boolean;
  apply_fee_on_exit?: boolean;
  slippage_rate?: number;
  entry_slippage_rate?: number | null;
  exit_slippage_rate?: number | null;
  execution_policy?: "next_open" | "signal_close";
  benchmark_enabled?: boolean;
  run_tag?: string | null;
  note?: string | null;
};

export type WalkforwardSegment = {
  segment_index: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  linked_run_id?: string | null;
  status: string;
  trade_count: number;
  gross_return_pct: number;
  net_return_pct: number;
  max_drawdown: number;
  win_rate: number;
  benchmark_buy_and_hold_return_pct: number;
  excess_return_pct: number;
  timeframe_mapping?: Record<string, string> | null;
};

export type WalkforwardSummary = {
  segment_count: number;
  completed_segment_count: number;
  total_net_return_pct: number;
  average_segment_return_pct: number;
  median_segment_return_pct: number;
  worst_segment_return_pct: number;
  best_segment_return_pct: number;
  average_max_drawdown: number;
  total_trade_count: number;
  benchmark_comparison_summary?: string | null;
};

export type WalkforwardDiagnostics = {
  profitable_segments: number;
  losing_segments: number;
  segments_beating_benchmark: number;
  segments_underperforming_benchmark: number;
};

export type WalkforwardRunResponse = {
  walkforward_run_id: string;
  rerun_of_walkforward_run_id?: string | null;
  request_hash: string;
  created_at: string;
  strategy_id: string;
  strategy_version: string;
  code_version: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string> | null;
  requested_period: { start_date: string; end_date: string };
  train_window_size: number;
  test_window_size: number;
  step_size: number;
  window_unit: "candles" | "days";
  walkforward_mode: "rolling" | "anchored";
  execution_config: BacktestRunResponse["execution_config"];
  params_snapshot: Record<string, unknown>;
  benchmark_enabled: boolean;
  run_tag?: string | null;
  note?: string | null;
  segments: WalkforwardSegment[];
  summary: WalkforwardSummary;
  diagnostics: WalkforwardDiagnostics;
  interpretation_summary: string;
};

export type WalkforwardListItem = {
  walkforward_run_id: string;
  created_at: string;
  strategy_id: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string> | null;
  requested_period: { start_date: string; end_date: string };
  walkforward_mode: "rolling" | "anchored";
  segment_count: number;
  completed_segment_count: number;
  total_net_return_pct: number;
  average_segment_return_pct: number;
  profitable_segments: number;
  segments_beating_benchmark: number;
};

export type WalkforwardCompareItem = {
  walkforward_run_id: string;
  created_at: string;
  strategy_id: string;
  symbol: string;
  timeframe_mapping?: Record<string, string> | null;
  timeframe_mapping_summary?: string | null;
  walkforward_mode: "rolling" | "anchored";
  segment_count: number;
  total_net_return_pct: number;
  average_segment_return_pct: number;
  worst_segment_return_pct: number;
  best_segment_return_pct: number;
  segments_beating_benchmark: number;
  profitable_segments: number;
};

export type WalkforwardCompareResponse = {
  compared_count: number;
  best_walkforward_run_id: string;
  items: WalkforwardCompareItem[];
};

export type WalkforwardJob = {
  job_id: string;
  job_type: string;
  status: BacktestJobStatus;
  progress: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  related_walkforward_run_id?: string | null;
  error_summary?: string | null;
  error_detail?: string | null;
  retry_count: number;
  parent_job_id?: string | null;
  request_hash: string;
  duplicate_of_job_id?: string | null;
  segment_total?: number | null;
  segment_completed?: number | null;
  failed_segment_index?: number | null;
  request: WalkforwardRunRequest;
};

export type WalkforwardBatchRunRequest = {
  strategy_id: string;
  symbols: string[];
  timeframe: string;
  timeframe_mapping?: Record<string, string>;
  start_date: string;
  end_date: string;
  train_window_size: number;
  test_window_size: number;
  step_size: number;
  window_unit: "candles" | "days";
  walkforward_modes: ("rolling" | "anchored")[];
  params?: Record<string, number>;
  fee_rate?: number;
  entry_fee_rate?: number | null;
  exit_fee_rate?: number | null;
  apply_fee_on_entry?: boolean;
  apply_fee_on_exit?: boolean;
  slippage_rate?: number;
  entry_slippage_rate?: number | null;
  exit_slippage_rate?: number | null;
  execution_policy?: "next_open" | "signal_close";
  benchmark_enabled?: boolean;
  use_jobs?: boolean;
};

export type WalkforwardBatchRunResponse = {
  batch_id: string;
  created_at: string;
  total_requested: number;
  items: {
    symbol: string;
    walkforward_mode: "rolling" | "anchored";
    status: string;
    job_id?: string | null;
    walkforward_run_id?: string | null;
  }[];
};

export type SweepRunRequest = {
  strategy_id: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string>;
  start_date: string;
  end_date: string;
  sweep_space: Record<string, Array<number | string>>;
  benchmark_enabled?: boolean;
  fee_rate?: number;
  entry_fee_rate?: number | null;
  exit_fee_rate?: number | null;
  apply_fee_on_entry?: boolean;
  apply_fee_on_exit?: boolean;
  slippage_rate?: number;
  entry_slippage_rate?: number | null;
  exit_slippage_rate?: number | null;
  execution_policy?: "next_open" | "signal_close";
  use_job?: boolean;
  run_tag?: string | null;
  note?: string | null;
};

export type SweepCombinationResult = {
  combination_id: string;
  params_snapshot: Record<string, unknown>;
  related_run_id?: string | null;
  gross_return_pct: number;
  net_return_pct: number;
  max_drawdown: number;
  trade_count: number;
  win_rate: number;
  benchmark_buy_and_hold_return_pct: number;
  excess_return_pct: number;
  status: "completed" | "failed";
  error_summary?: string | null;
};

export type SweepRunResponse = {
  sweep_run_id: string;
  rerun_of_sweep_run_id?: string | null;
  request_hash: string;
  created_at: string;
  strategy_id: string;
  strategy_version: string;
  code_version: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string> | null;
  start_date: string;
  end_date: string;
  execution_config: BacktestRunResponse["execution_config"];
  benchmark_enabled: boolean;
  sweep_space: Record<string, Array<number | string>>;
  total_combinations: number;
  completed_combinations: number;
  failed_combinations: number;
  run_tag?: string | null;
  note?: string | null;
  ranking_summary: {
    best_by_net_return?: SweepCombinationResult | null;
    best_by_excess_return?: SweepCombinationResult | null;
    lowest_drawdown_group: SweepCombinationResult[];
    top_n: SweepCombinationResult[];
    profitable_count: number;
    losing_count: number;
    average_net_return: number;
    median_net_return: number;
    average_max_drawdown: number;
  };
  results: SweepCombinationResult[];
};

export type SweepListItem = {
  sweep_run_id: string;
  created_at: string;
  strategy_id: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  timeframe_mapping?: Record<string, string> | null;
  total_combinations: number;
  completed_combinations: number;
  failed_combinations: number;
  top_net_return_pct: number;
  average_net_return: number;
};

export type SweepJob = {
  job_id: string;
  job_type: string;
  status: BacktestJobStatus;
  progress: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  related_sweep_run_id?: string | null;
  total_combinations?: number | null;
  completed_combinations?: number | null;
  failed_combinations?: number | null;
  error_summary?: string | null;
  error_detail?: string | null;
  retry_count: number;
  parent_job_id?: string | null;
  request_hash: string;
  duplicate_of_job_id?: string | null;
  request: SweepRunRequest;
};

export type MarketDataCollectRequest = {
  source?: string;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  overwrite?: boolean;
  dry_run?: boolean;
  use_job?: boolean;
};

export type MarketDataUpdateRequest = {
  source?: string;
  symbol: string;
  timeframe: string;
  end_date?: string | null;
  use_job?: boolean;
};

export type MarketDataBatchRequest = {
  source?: string;
  symbols: string[];
  timeframes: string[];
  start_date?: string | null;
  end_date?: string | null;
  mode?: "full_collect" | "incremental_update";
  validate_after_collect?: boolean;
  use_job?: boolean;
  overwrite?: boolean;
  dry_run?: boolean;
};

export type MarketDataDatasetItem = {
  dataset_id: string;
  source: string;
  symbol: string;
  timeframe: string;
  start_at?: string | null;
  end_at?: string | null;
  row_count: number;
  quality_status: "pass" | "warning" | "fail";
  updated_at: string;
};

export type MarketDataDetail = {
  manifest: {
    dataset_id: string;
    source: string;
    exchange?: string | null;
    symbol: string;
    timeframe: string;
    start_at?: string | null;
    end_at?: string | null;
    row_count: number;
    created_at: string;
    updated_at: string;
    data_signature: string;
    quality_status: "pass" | "warning" | "fail";
    quality_report_summary: string;
    collector_version: string;
    code_version: string;
    last_checked_at?: string | null;
    path: string;
    notes?: string | null;
  };
  quality_report: {
    status: "pass" | "warning" | "fail";
    row_count: number;
    duplicate_count: number;
    missing_interval_count: number;
    null_count: number;
    invalid_ohlc_count: number;
    suspicious_gap_count: number;
    summary_message: string;
    detail_messages: string[];
  };
};

export type MarketDataOperationResponse = {
  mode: "sync" | "job";
  job_id?: string | null;
  message?: string | null;
  result?: {
    dataset_id: string;
    source: string;
    symbol: string;
    timeframe: string;
    requested_period: { start_date: string; end_date: string };
    fetched_count: number;
    saved_count: number;
    duplicate_removed_count: number;
    actual_range: { start_at?: string | null; end_at?: string | null };
    dataset_path: string;
    data_signature: string;
    quality_status: "pass" | "warning" | "fail";
  } | null;
};

export type MarketDataBatchResult = {
  mode: "sync" | "job";
  batch_id: string;
  total_requested_combinations: number;
  completed_combinations: number;
  failed_combinations: number;
  skipped_combinations: number;
  created_datasets: number;
  updated_datasets: number;
  pass_count: number;
  warning_count: number;
  fail_count: number;
  job_id?: string | null;
  items: {
    source: string;
    symbol: string;
    timeframe: string;
    status: "completed" | "failed" | "skipped";
    dataset_id?: string | null;
    quality_status?: "pass" | "warning" | "fail" | null;
    fetched_count: number;
    saved_count: number;
    message?: string | null;
  }[];
  message?: string | null;
};

export type MarketDataSummary = {
  total_datasets: number;
  available_symbols: string[];
  available_timeframes: string[];
  pass_count: number;
  warning_count: number;
  fail_count: number;
  latest_updated_at?: string | null;
  by_symbol: Record<
    string,
    {
      timeframes: Record<
        string,
        {
          dataset_id?: string | null;
          quality_status?: "pass" | "warning" | "fail" | null;
          updated_at?: string | null;
          row_count?: number;
        }
      >;
      pass_count: number;
      warning_count: number;
      fail_count: number;
    }
  >;
};

export type MarketDataJob = {
  job_id: string;
  job_type: string;
  status: BacktestJobStatus;
  progress: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  related_dataset_id?: string | null;
  error_summary?: string | null;
  error_detail?: string | null;
  retry_count: number;
  parent_job_id?: string | null;
  request_hash: string;
  duplicate_of_job_id?: string | null;
  batch_id?: string | null;
  total_combinations?: number | null;
  completed_combinations?: number | null;
  failed_combinations?: number | null;
  current_symbol?: string | null;
  current_timeframe?: string | null;
  combination_results?: Record<string, unknown>[] | null;
  request: Record<string, unknown>;
};

export type MarketDataPreview = {
  dataset_id: string;
  timeframe: string;
  total_rows: number;
  rows: {
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
};
