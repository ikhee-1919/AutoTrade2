"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import { WalkforwardCompareResponse, WalkforwardListItem } from "@/types/api";

export default function WalkforwardComparePage() {
  const [runs, setRuns] = useState<WalkforwardListItem[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<WalkforwardCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canCompare = useMemo(() => selected.length >= 2, [selected]);

  useEffect(() => {
    async function load() {
      try {
        const items = await api.listWalkforwardRuns(40);
        setRuns(items);
      } catch {
        setRuns([]);
      }
    }
    void load();
  }, []);

  const toggle = (id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
  };

  const compare = async () => {
    if (!canCompare) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.compareWalkforwardRuns(selected);
      setComparison(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const exportCsv = async () => {
    if (!canCompare) return;
    setError(null);
    try {
      const csvText = await api.exportWalkforwardCompareCsv(selected);
      const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "walkforward_compare.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  };

  return (
    <div>
      <h1>Walk-Forward 비교</h1>
      <p className="small">여러 walk-forward 실행을 선택해 세그먼트 일관성을 비교합니다.</p>
      <SectionCard title="실행 선택" description="2개 이상 선택 후 비교">
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <button type="button" onClick={compare} disabled={!canCompare || loading}>
            {loading ? "비교 중..." : "선택 항목 비교"}
          </button>
          <button type="button" onClick={exportCsv} disabled={!canCompare || loading}>
            CSV 내보내기
          </button>
          <Link href="/walkforward">walk-forward 메인으로 돌아가기</Link>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {runs.length === 0 ? (
          <div className="placeholder">비교할 walk-forward 이력이 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>선택</th>
                <th>생성시각</th>
                <th>run_id</th>
                <th>전략/종목</th>
                <th>tf mapping</th>
                <th>mode</th>
                <th>segment</th>
                <th>총 Net</th>
                <th>평균 Segment</th>
                <th>Benchmark 초과</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.walkforward_run_id}>
                  <td>
                    <input
                      type="checkbox"
                      style={{ width: "auto" }}
                      checked={selected.includes(run.walkforward_run_id)}
                      onChange={() => toggle(run.walkforward_run_id)}
                    />
                  </td>
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
                  <td>{run.walkforward_mode}</td>
                  <td>
                    {run.completed_segment_count}/{run.segment_count}
                  </td>
                  <td>{run.total_net_return_pct.toFixed(2)}%</td>
                  <td>{run.average_segment_return_pct.toFixed(2)}%</td>
                  <td>{run.segments_beating_benchmark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <SectionCard title="비교 결과" description="성과 및 벤치마크 일관성 비교">
        {!comparison ? (
          <div className="placeholder">비교할 이력 2개 이상을 선택하세요.</div>
        ) : (
          <>
            <p className="small">best run: {comparison.best_walkforward_run_id}</p>
            <div className="grid two">
              {comparison.items.map((item) => (
                <div key={item.walkforward_run_id} className="card">
                  <p className="small">
                    <Link href={`/walkforward/${item.walkforward_run_id}`}>
                      {item.walkforward_run_id.slice(0, 8)}
                    </Link>
                  </p>
                  <p className="small">mode: {item.walkforward_mode}</p>
                  <p className="small">tf map: {item.timeframe_mapping_summary ?? "-"}</p>
                  <p>총 Net: {item.total_net_return_pct.toFixed(2)}%</p>
                  <p className="small">평균 Segment: {item.average_segment_return_pct.toFixed(2)}%</p>
                  <p className="small">
                    best/worst: {item.best_segment_return_pct.toFixed(2)}% /{" "}
                    {item.worst_segment_return_pct.toFixed(2)}%
                  </p>
                  <p className="small">수익 Segment: {item.profitable_segments}</p>
                  <p className="small">Benchmark 초과: {item.segments_beating_benchmark}</p>
                </div>
              ))}
            </div>
          </>
        )}
      </SectionCard>
    </div>
  );
}
