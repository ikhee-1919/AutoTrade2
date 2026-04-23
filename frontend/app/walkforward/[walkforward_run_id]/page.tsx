"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { WalkforwardSegmentChart } from "@/components/walkforward-segment-chart";
import { api } from "@/lib/api";
import { WalkforwardRunResponse } from "@/types/api";

export default function WalkforwardDetailPage() {
  const params = useParams<{ walkforward_run_id: string }>();
  const runId = params.walkforward_run_id;
  const [data, setData] = useState<WalkforwardRunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (!runId) return;
      setLoading(true);
      setError(null);
      try {
        const detail = await api.getWalkforwardDetail(runId);
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
    return <div className="placeholder">walk-forward 상세 로딩 중...</div>;
  }
  if (error || !data) {
    return (
      <div className="grid">
        <p className="error">{error ?? "walk-forward 상세를 불러오지 못했습니다."}</p>
        <Link href="/walkforward">walk-forward 페이지로 돌아가기</Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Walk-Forward 상세 리포트</h1>
      <p className="small">walkforward_run_id: {data.walkforward_run_id}</p>

      <SectionCard title="핵심 요약" description="세그먼트 기반 성과 해석">
        <div className="card">
          <p>{data.interpretation_summary}</p>
          <p className="small">
            strategy={data.strategy_id} v{data.strategy_version} / code={data.code_version}
          </p>
        </div>
        <div className="grid two">
          <div className="card">
            <div className="small">Segment 수</div>
            <strong>
              {data.summary.completed_segment_count}/{data.summary.segment_count}
            </strong>
          </div>
          <div className="card">
            <div className="small">총 Net 수익률</div>
            <strong>{data.summary.total_net_return_pct.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">평균 Segment 수익률</div>
            <strong>{data.summary.average_segment_return_pct.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">중앙 Segment 수익률</div>
            <strong>{data.summary.median_segment_return_pct.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">Best/Worst</div>
            <strong>
              {data.summary.best_segment_return_pct.toFixed(2)}% /{" "}
              {data.summary.worst_segment_return_pct.toFixed(2)}%
            </strong>
          </div>
          <div className="card">
            <div className="small">평균 MDD</div>
            <strong>{data.summary.average_max_drawdown.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">수익 세그먼트</div>
            <strong>{data.diagnostics.profitable_segments}</strong>
          </div>
          <div className="card">
            <div className="small">손실 세그먼트</div>
            <strong>{data.diagnostics.losing_segments}</strong>
          </div>
          <div className="card">
            <div className="small">Benchmark 초과</div>
            <strong>{data.diagnostics.segments_beating_benchmark}</strong>
          </div>
          <div className="card">
            <div className="small">Benchmark 하회</div>
            <strong>{data.diagnostics.segments_underperforming_benchmark}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Segment 수익률 시각화" description="세그먼트별 순수익률과 benchmark 초과 여부">
        <WalkforwardSegmentChart segments={data.segments} />
      </SectionCard>

      <SectionCard title="세그먼트 상세" description="test 구간 성과 및 linked backtest run">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>train 기간</th>
              <th>test 기간</th>
              <th>Net(%)</th>
              <th>MDD(%)</th>
              <th>거래수</th>
              <th>Win Rate</th>
              <th>Benchmark</th>
              <th>Excess</th>
              <th>run</th>
            </tr>
          </thead>
          <tbody>
            {data.segments.map((seg) => (
              <tr key={`${seg.segment_index}-${seg.test_start}`}>
                <td>{seg.segment_index}</td>
                <td>
                  {seg.train_start} ~ {seg.train_end}
                </td>
                <td>
                  {seg.test_start} ~ {seg.test_end}
                </td>
                <td>{seg.net_return_pct.toFixed(2)}%</td>
                <td>{seg.max_drawdown.toFixed(2)}%</td>
                <td>{seg.trade_count}</td>
                <td>{seg.win_rate.toFixed(2)}%</td>
                <td>{seg.benchmark_buy_and_hold_return_pct.toFixed(2)}%</td>
                <td>{seg.excess_return_pct.toFixed(2)}%</td>
                <td>
                  {seg.linked_run_id ? (
                    <Link href={`/backtests/${seg.linked_run_id}`}>{seg.linked_run_id.slice(0, 8)}</Link>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      <SectionCard title="실행 메타" description="재현성 검증 메타데이터">
        <table>
          <tbody>
            <tr>
              <th>요청 기간</th>
              <td>
                {data.requested_period.start_date} ~ {data.requested_period.end_date}
              </td>
            </tr>
            <tr>
              <th>window</th>
              <td>
                train={data.train_window_size}, test={data.test_window_size}, step={data.step_size},{" "}
                unit={data.window_unit}
              </td>
            </tr>
            <tr>
              <th>walkforward_mode</th>
              <td>{data.walkforward_mode}</td>
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
              <th>execution_policy</th>
              <td>{data.execution_config.execution_policy}</td>
            </tr>
            <tr>
              <th>request_hash</th>
              <td>{data.request_hash}</td>
            </tr>
            <tr>
              <th>params_snapshot</th>
              <td>
                <pre>{JSON.stringify(data.params_snapshot, null, 2)}</pre>
              </td>
            </tr>
            <tr>
              <th>rerun_of</th>
              <td>{data.rerun_of_walkforward_run_id ?? "-"}</td>
            </tr>
          </tbody>
        </table>
      </SectionCard>

      <Link href="/walkforward">walk-forward 목록으로 돌아가기</Link>
    </div>
  );
}
