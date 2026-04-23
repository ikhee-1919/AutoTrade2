"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { EquityCurveChart } from "@/components/equity-curve-chart";
import { api } from "@/lib/api";
import { BacktestRunResponse } from "@/types/api";

export default function BacktestDetailPage() {
  const params = useParams<{ run_id: string }>();
  const runId = params.run_id;

  const [data, setData] = useState<BacktestRunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (!runId) return;
      setLoading(true);
      setError(null);
      try {
        const detail = await api.getBacktestDetail(runId);
        setData(detail);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [runId]);

  if (loading) {
    return <div className="placeholder">상세 리포트 로딩 중...</div>;
  }

  if (error || !data) {
    return (
      <div className="grid">
        <p className="error">{error ?? "상세 리포트를 불러올 수 없습니다."}</p>
        <Link href="/backtests">백테스트 페이지로 돌아가기</Link>
      </div>
    );
  }

  const wins = data.trades.filter((trade) => trade.pnl > 0);
  const losses = data.trades.filter((trade) => trade.pnl <= 0);
  const maxRejectCount = Math.max(1, ...Object.values(data.diagnostics.reject_reason_counts));
  const totalRegimeCount = Math.max(
    1,
    Object.values(data.diagnostics.regime_counts).reduce((acc, cur) => acc + cur, 0),
  );

  const summarySentence = (() => {
    if (data.summary.trade_count === 0) {
      return "거래가 거의 발생하지 않아 전략 진입 조건이 매우 보수적으로 작동했습니다.";
    }
    if (data.summary.net_return_pct >= 0 && data.summary.max_drawdown < 10) {
      return "수익성과 안정성 균형이 비교적 양호한 실행입니다.";
    }
    if (data.summary.win_rate < 40 && data.summary.max_drawdown >= 15) {
      return "승률과 낙폭이 모두 불리해 리스크 관리/진입 필터 재점검이 필요합니다.";
    }
    if (data.summary.net_return_pct < 0) {
      return "손실 구간이 우세하여 파라미터 또는 시장 국면 적합성 검토가 필요합니다.";
    }
    return "일부 지표는 양호하지만 보수적인 재검증이 권장됩니다.";
  })();

  return (
    <div>
      <h1>백테스트 상세 리포트</h1>
      <p className="small">run_id: {data.run_id}</p>

      <SectionCard title="핵심 요약" description="룰 기반 요약 인사이트">
        <div className="card">
          <p>{summarySentence}</p>
          <p className="small">
            strategy={data.strategy_id} v{data.strategy_version} / code={data.code_version}
          </p>
        </div>
      </SectionCard>

      <SectionCard title="실행 메타" description="재현성 검증을 위한 실행 스냅샷">
        <table>
          <tbody>
            <tr>
              <th>전략</th>
              <td>
                {data.strategy_id} ({data.strategy_version})
              </td>
            </tr>
            <tr>
              <th>코드 버전</th>
              <td>{data.code_version}</td>
            </tr>
            <tr>
              <th>체결 정책</th>
              <td>{data.execution_config.execution_policy}</td>
            </tr>
            <tr>
              <th>종목/타임프레임</th>
              <td>
                {data.symbol} / {data.timeframe}
              </td>
            </tr>
            <tr>
              <th>timeframe_mapping</th>
              <td>
                {data.timeframe_mapping
                  ? Object.entries(data.timeframe_mapping)
                      .map(([role, tf]) => `${role}:${tf}`)
                      .join(", ")
                  : "-"}
              </td>
            </tr>
            <tr>
              <th>기간</th>
              <td>
                {data.start_date} ~ {data.end_date}
              </td>
            </tr>
            <tr>
              <th>params_hash</th>
              <td>{data.params_hash}</td>
            </tr>
            <tr>
              <th>params_snapshot</th>
              <td>
                <pre>{JSON.stringify(data.params_snapshot, null, 2)}</pre>
              </td>
            </tr>
            <tr>
              <th>data_signature</th>
              <td>
                candles={data.data_signature.candle_count}, hash={data.data_signature.candles_hash.slice(0, 12)}
              </td>
            </tr>
            <tr>
              <th>selected_datasets_by_role</th>
              <td>
                <pre>{JSON.stringify(data.selected_datasets_by_role ?? {}, null, 2)}</pre>
              </td>
            </tr>
            <tr>
              <th>rerun_of</th>
              <td>{data.rerun_of_run_id ?? "-"}</td>
            </tr>
          </tbody>
        </table>
      </SectionCard>

      <SectionCard title="성과 요약" description="핵심 성과 지표">
        <div className="grid two">
          <div className="card">
            <div className="small">Gross 수익률</div>
            <strong>{data.summary.gross_return_pct.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">Net 수익률</div>
            <strong>{data.summary.net_return_pct.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">MDD</div>
            <strong>{data.summary.max_drawdown.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">승률</div>
            <strong>{data.summary.win_rate.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">거래 수</div>
            <strong>{data.summary.trade_count}</strong>
          </div>
          <div className="card">
            <div className="small">총 거래비용</div>
            <strong>{data.summary.total_trading_cost.toFixed(4)}</strong>
          </div>
          <div className="card">
            <div className="small">Cost Drag</div>
            <strong>{data.summary.cost_drag_pct.toFixed(2)}%</strong>
          </div>
          {data.benchmark ? (
            <div className="card">
              <div className="small">Buy & Hold</div>
              <strong>{data.benchmark.benchmark_buy_and_hold_return_pct.toFixed(2)}%</strong>
            </div>
          ) : null}
          {data.benchmark ? (
            <div className="card">
              <div className="small">Excess Return</div>
              <strong>{data.benchmark.strategy_excess_return_pct.toFixed(2)}%</strong>
            </div>
          ) : null}
        </div>
      </SectionCard>

      <SectionCard title="자산곡선" description="백테스트 기간 누적 자산 추이">
        <EquityCurveChart points={data.equity_curve} benchmarkPoints={data.benchmark?.benchmark_curve ?? []} />
      </SectionCard>

      <SectionCard title="비용 요약" description="수수료/슬리피지가 성과에 미친 영향">
        <div className="grid two">
          <div className="card">
            <div className="small">총 수수료</div>
            <strong>{data.summary.total_fees_paid.toFixed(4)}</strong>
          </div>
          <div className="card">
            <div className="small">총 슬리피지 비용</div>
            <strong>{data.summary.total_slippage_cost.toFixed(4)}</strong>
          </div>
          <div className="card">
            <div className="small">총 거래비용</div>
            <strong>{data.summary.total_trading_cost.toFixed(4)}</strong>
          </div>
          <div className="card">
            <div className="small">거래당 평균 비용</div>
            <strong>
              {(data.summary.total_trading_cost / Math.max(1, data.summary.trade_count)).toFixed(4)}
            </strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="거래 손익 분포" description="이익/손실 개수를 직관적으로 표시">
        <div className="grid two">
          <div className="card">
            <div className="small">이익 거래</div>
            <p className="metric-positive">{wins.length}건</p>
          </div>
          <div className="card">
            <div className="small">손실/보합 거래</div>
            <p className="metric-negative">{losses.length}건</p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="거래 로그" description="진입/청산 단위 기록">
        {data.trades.length === 0 ? (
          <div className="placeholder">저장된 거래 로그가 없습니다.</div>
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
                <th>Total Cost</th>
                <th>사유</th>
              </tr>
            </thead>
            <tbody>
              {data.trades.map((trade, idx) => (
                <tr key={`${trade.entry_time}-${idx}`}>
                  <td>{new Date(trade.entry_time).toLocaleString()}</td>
                  <td>{new Date(trade.exit_time).toLocaleString()}</td>
                  <td>{trade.entry_price.toLocaleString()}</td>
                  <td>{trade.exit_price.toLocaleString()}</td>
                  <td>{trade.gross_pnl.toFixed(2)}</td>
                  <td>{trade.net_pnl.toFixed(2)}</td>
                  <td>{trade.total_fees.toFixed(4)}</td>
                  <td>{trade.total_slippage_cost.toFixed(4)}</td>
                  <td>{trade.total_trading_cost.toFixed(4)}</td>
                  <td>{trade.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <SectionCard title="진단 분포" description="reject reason / regime 분포">
        <div className="grid two">
          <div className="card">
            <h2>Reject Reasons</h2>
            {Object.entries(data.diagnostics.reject_reason_counts).map(([reason, count]) => (
              <div key={reason} style={{ marginBottom: 8 }}>
                <div className="small">
                  {reason}: {count}
                </div>
                <div className="progress-wrap">
                  <div
                    className="progress-fill"
                    style={{ width: `${(count / maxRejectCount) * 100}%`, background: "#ef4444" }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="card">
            <h2>Regime Counts</h2>
            {Object.entries(data.diagnostics.regime_counts).map(([regime, count]) => (
              <div key={regime} style={{ marginBottom: 8 }}>
                <div className="small">
                  {regime}: {count} ({((count / totalRegimeCount) * 100).toFixed(1)}%)
                </div>
                <div className="progress-wrap">
                  <div
                    className="progress-fill"
                    style={{ width: `${(count / totalRegimeCount) * 100}%`, background: "#1d4ed8" }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </SectionCard>

      <Link href="/backtests">백테스트 목록으로 돌아가기</Link>
    </div>
  );
}
