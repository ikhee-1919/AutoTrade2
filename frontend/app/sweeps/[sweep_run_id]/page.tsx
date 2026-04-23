"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import { SweepRunResponse } from "@/types/api";

export default function SweepDetailPage() {
  const params = useParams<{ sweep_run_id: string }>();
  const sweepRunId = params.sweep_run_id;
  const [data, setData] = useState<SweepRunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!sweepRunId) return;
      setLoading(true);
      setError(null);
      try {
        const detail = await api.getSweepDetail(sweepRunId);
        setData(detail);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [sweepRunId]);

  if (loading) return <div className="placeholder">sweep 상세 로딩 중...</div>;
  if (error || !data) {
    return (
      <div className="grid">
        <p className="error">{error ?? "sweep 상세를 불러올 수 없습니다."}</p>
        <Link href="/sweeps">sweep 목록으로 돌아가기</Link>
      </div>
    );
  }

  return (
    <div>
      <h1>파라미터 스윕 상세</h1>
      <p className="small">sweep_run_id: {data.sweep_run_id}</p>

      <SectionCard title="요약" description="상위 조합 및 통계">
        <div className="grid two">
          <div className="card">
            <div className="small">조합 완료</div>
            <strong>
              {data.completed_combinations}/{data.total_combinations}
            </strong>
          </div>
          <div className="card">
            <div className="small">실패 조합</div>
            <strong>{data.failed_combinations}</strong>
          </div>
          <div className="card">
            <div className="small">평균 Net</div>
            <strong>{data.ranking_summary.average_net_return.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">중앙 Net</div>
            <strong>{data.ranking_summary.median_net_return.toFixed(2)}%</strong>
          </div>
          <div className="card">
            <div className="small">수익 조합 수</div>
            <strong>{data.ranking_summary.profitable_count}</strong>
          </div>
          <div className="card">
            <div className="small">손실 조합 수</div>
            <strong>{data.ranking_summary.losing_count}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="실행 메타" description="재현성 확인">
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
              <th>종목/기간</th>
              <td>
                {data.symbol} / {data.start_date} ~ {data.end_date}
              </td>
            </tr>
            <tr>
              <th>timeframe_mapping</th>
              <td>
                {data.timeframe_mapping
                  ? Object.entries(data.timeframe_mapping)
                      .map(([role, tf]) => `${role}:${tf}`)
                      .join(", ")
                  : data.timeframe}
              </td>
            </tr>
            <tr>
              <th>sweep_space</th>
              <td>
                <pre>{JSON.stringify(data.sweep_space, null, 2)}</pre>
              </td>
            </tr>
          </tbody>
        </table>
      </SectionCard>

      <SectionCard title="Top Combinations" description="net return 기준 상위 조합">
        {data.ranking_summary.top_n.length === 0 ? (
          <div className="placeholder">완료된 조합이 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>combination</th>
                <th>params</th>
                <th>Net</th>
                <th>MDD</th>
                <th>Excess</th>
                <th>거래수</th>
                <th>run</th>
              </tr>
            </thead>
            <tbody>
              {data.ranking_summary.top_n.map((item) => (
                <tr key={item.combination_id}>
                  <td>{item.combination_id}</td>
                  <td>
                    <pre>{JSON.stringify(item.params_snapshot, null, 2)}</pre>
                  </td>
                  <td>{item.net_return_pct.toFixed(2)}%</td>
                  <td>{item.max_drawdown.toFixed(2)}%</td>
                  <td>{item.excess_return_pct.toFixed(2)}%</td>
                  <td>{item.trade_count}</td>
                  <td>
                    {item.related_run_id ? (
                      <Link href={`/backtests/${item.related_run_id}`}>{item.related_run_id.slice(0, 8)}</Link>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <SectionCard title="전체 조합 결과" description="completed / failed 모두 표시">
        <table>
          <thead>
            <tr>
              <th>combination</th>
              <th>status</th>
              <th>Net</th>
              <th>MDD</th>
              <th>error</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((item) => (
              <tr key={`all-${item.combination_id}`}>
                <td>{item.combination_id}</td>
                <td>{item.status}</td>
                <td>{item.net_return_pct.toFixed(2)}%</td>
                <td>{item.max_drawdown.toFixed(2)}%</td>
                <td>{item.error_summary ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      <Link href="/sweeps">sweep 목록으로 돌아가기</Link>
    </div>
  );
}
