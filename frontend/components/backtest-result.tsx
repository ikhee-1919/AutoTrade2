import Link from "next/link";

import { BacktestRunResponse } from "@/types/api";

type BacktestResultProps = {
  result: BacktestRunResponse | null;
};

export function BacktestResult({ result }: BacktestResultProps) {
  if (!result) {
    return <div className="placeholder">아직 실행 결과가 없습니다.</div>;
  }

  const { summary } = result;
  return (
    <div className="grid">
      <div className="card">
        <div className="small">run_id</div>
        <Link href={`/backtests/${result.run_id}`}>{result.run_id}</Link>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="small">Gross 수익률</div>
          <strong>{summary.gross_return_pct.toFixed(2)}%</strong>
        </div>
        <div className="card">
          <div className="small">Net 수익률</div>
          <strong>{summary.net_return_pct.toFixed(2)}%</strong>
        </div>
        <div className="card">
          <div className="small">거래 수</div>
          <strong>{summary.trade_count}</strong>
        </div>
        <div className="card">
          <div className="small">승률</div>
          <strong>{summary.win_rate.toFixed(2)}%</strong>
        </div>
        <div className="card">
          <div className="small">MDD</div>
          <strong>{summary.max_drawdown.toFixed(2)}%</strong>
        </div>
        <div className="card">
          <div className="small">총 거래비용</div>
          <strong>{summary.total_trading_cost.toFixed(4)}</strong>
        </div>
        <div className="card">
          <div className="small">Cost Drag</div>
          <strong>{summary.cost_drag_pct.toFixed(2)}%</strong>
        </div>
        {result.benchmark ? (
          <div className="card">
            <div className="small">Buy & Hold</div>
            <strong>{result.benchmark.benchmark_buy_and_hold_return_pct.toFixed(2)}%</strong>
          </div>
        ) : null}
      </div>

      <div className="card">
        <h2>거래 로그</h2>
        {result.trades.length === 0 ? (
          <div className="placeholder">거래가 발생하지 않았습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>진입시각</th>
                <th>청산시각</th>
                <th>진입가</th>
                <th>청산가</th>
                <th>Gross(%)</th>
                <th>Net(%)</th>
                <th>Fees</th>
                <th>Slippage</th>
                <th>사유</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.map((trade, idx) => (
                <tr key={`${trade.entry_time}-${idx}`}>
                  <td>{new Date(trade.entry_time).toLocaleString()}</td>
                  <td>{new Date(trade.exit_time).toLocaleString()}</td>
                  <td>{trade.entry_price.toLocaleString()}</td>
                  <td>{trade.exit_price.toLocaleString()}</td>
                  <td>{trade.gross_pnl.toFixed(2)}</td>
                  <td>{trade.net_pnl.toFixed(2)}</td>
                  <td>{trade.total_fees.toFixed(4)}</td>
                  <td>{trade.total_slippage_cost.toFixed(4)}</td>
                  <td>{trade.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>진입/거절 요약</h2>
        <pre>{JSON.stringify(result.diagnostics, null, 2)}</pre>
      </div>
    </div>
  );
}
