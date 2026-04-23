"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import { BacktestCompareResponse, BacktestRunResponse, RecentBacktestItem } from "@/types/api";

type BacktestComparePanelProps = {
  history: RecentBacktestItem[];
  onRefresh: () => Promise<void>;
  onRerunComplete: (result: BacktestRunResponse) => void;
};

export function BacktestComparePanel({
  history,
  onRefresh,
  onRerunComplete,
}: BacktestComparePanelProps) {
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [rerunLoadingId, setRerunLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<BacktestCompareResponse | null>(null);

  const canCompare = useMemo(() => selectedRunIds.length >= 2, [selectedRunIds]);

  const toggle = (runId: string) => {
    setSelectedRunIds((prev) =>
      prev.includes(runId) ? prev.filter((id) => id !== runId) : [...prev, runId],
    );
  };

  const compare = async () => {
    if (!canCompare) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.compareBacktests(selectedRunIds);
      setComparison(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const rerun = async (runId: string) => {
    setRerunLoadingId(runId);
    setError(null);
    try {
      const result = await api.rerunBacktest(runId);
      onRerunComplete(result);
      await onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setRerunLoadingId(null);
    }
  };

  return (
    <div className="grid">
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" onClick={compare} disabled={!canCompare || loading}>
          {loading ? "비교 중..." : "선택 항목 비교"}
        </button>
        <button type="button" onClick={() => void onRefresh()} disabled={loading}>
          이력 새로고침
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <table>
        <thead>
          <tr>
            <th>선택</th>
            <th>실행시각</th>
            <th>run_id</th>
            <th>code</th>
            <th>전략</th>
            <th>종목</th>
            <th>기간</th>
            <th>params_hash</th>
            <th>캔들 수</th>
            <th>tf mapping</th>
            <th>수익률</th>
            <th>거래수</th>
            <th>재실행</th>
          </tr>
        </thead>
        <tbody>
          {history.map((run) => (
            <tr key={run.run_id}>
              <td>
                <input
                  type="checkbox"
                  style={{ width: "auto" }}
                  checked={selectedRunIds.includes(run.run_id)}
                  onChange={() => toggle(run.run_id)}
                />
              </td>
              <td>{new Date(run.run_at).toLocaleString()}</td>
              <td>
                <Link href={`/backtests/${run.run_id}`}>{run.run_id.slice(0, 8)}</Link>
              </td>
              <td>{run.code_version}</td>
              <td>
                {run.strategy_id} ({run.strategy_version})
              </td>
              <td>{run.symbol}</td>
              <td>
                {run.start_date} ~ {run.end_date}
              </td>
              <td>{run.params_hash.slice(0, 8)}</td>
              <td>{run.data_signature.candle_count}</td>
              <td>{run.timeframe_mapping ? Object.entries(run.timeframe_mapping).map(([r, tf]) => `${r}:${tf}`).join(", ") : "-"}</td>
              <td>{run.total_return_pct.toFixed(2)}%</td>
              <td>{run.trade_count}</td>
              <td>
                <button
                  type="button"
                  onClick={() => void rerun(run.run_id)}
                  disabled={Boolean(rerunLoadingId)}
                >
                  {rerunLoadingId === run.run_id ? "실행 중..." : "다시 실행"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {comparison ? (
        <div className="card">
          <h2>비교 결과</h2>
          <p className="small">best run: {comparison.best_run_id}</p>
          <div className="grid two">
            {comparison.items.map((item) => (
              <div className="card" key={`summary-${item.run_id}`}>
                <p className="small">
                  <Link href={`/backtests/${item.run_id}`}>{item.run_id.slice(0, 8)}</Link>
                </p>
                <p className="small">code: {item.code_version}</p>
                <p className="small">tf map: {item.timeframe_mapping_summary ?? "-"}</p>
                <p>
                  Net 수익률:{" "}
                  <span className={item.net_return_pct >= 0 ? "metric-positive" : "metric-negative"}>
                    {item.net_return_pct.toFixed(2)}%
                  </span>
                </p>
                <p className="small">Gross: {item.gross_return_pct.toFixed(2)}%</p>
                <p className="small">MDD: {item.max_drawdown.toFixed(2)}%</p>
                <p className="small">평균이익: {item.summary_avg_profit.toFixed(2)}%</p>
                <p className="small">평균손실: {item.summary_avg_loss.toFixed(2)}%</p>
                <p className="small">총 비용: {item.total_trading_cost.toFixed(4)}</p>
                <p className="small">Cost Drag: {item.cost_drag_pct.toFixed(2)}%</p>
                <p className="small">B&H: {item.benchmark_buy_and_hold_return_pct.toFixed(2)}%</p>
                <p className="small">Excess: {item.strategy_excess_return_pct.toFixed(2)}%</p>
                <p className="small">주요 거절사유: {item.top_reject_reason ?? "-"}</p>
              </div>
            ))}
          </div>
          <table>
            <thead>
              <tr>
                <th>run_id</th>
                <th>Gross</th>
                <th>Net</th>
                <th>MDD</th>
                <th>승률</th>
                <th>거래수</th>
                <th>평균이익</th>
                <th>평균손실</th>
                <th>총비용</th>
                <th>CostDrag</th>
                <th>B&H</th>
                <th>Excess</th>
                <th>top reject</th>
                <th>수익률 gap</th>
                <th>MDD gap</th>
              </tr>
            </thead>
            <tbody>
              {comparison.items.map((item) => (
                <tr key={item.run_id}>
                  <td>
                    <Link href={`/backtests/${item.run_id}`}>{item.run_id.slice(0, 8)}</Link>
                  </td>
                  <td>{item.gross_return_pct.toFixed(2)}%</td>
                  <td>{item.net_return_pct.toFixed(2)}%</td>
                  <td>{item.max_drawdown.toFixed(2)}%</td>
                  <td>{item.win_rate.toFixed(2)}%</td>
                  <td>{item.trade_count}</td>
                  <td>{item.summary_avg_profit.toFixed(2)}%</td>
                  <td>{item.summary_avg_loss.toFixed(2)}%</td>
                  <td>{item.total_trading_cost.toFixed(4)}</td>
                  <td>{item.cost_drag_pct.toFixed(2)}%</td>
                  <td>{item.benchmark_buy_and_hold_return_pct.toFixed(2)}%</td>
                  <td>{item.strategy_excess_return_pct.toFixed(2)}%</td>
                  <td>{item.top_reject_reason ?? "-"}</td>
                  <td>{item.return_gap_vs_best.toFixed(2)}%</td>
                  <td>{item.mdd_gap_vs_best.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="placeholder">비교할 이력 2개 이상을 선택하세요.</div>
      )}
    </div>
  );
}
