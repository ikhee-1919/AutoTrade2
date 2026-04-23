import Link from "next/link";

import { WalkforwardRunResponse } from "@/types/api";

type WalkforwardResultProps = {
  result: WalkforwardRunResponse | null;
};

export function WalkforwardResult({ result }: WalkforwardResultProps) {
  if (!result) {
    return <div className="placeholder">아직 실행 결과가 없습니다.</div>;
  }
  return (
    <div className="grid">
      <div className="card">
        <div className="small">walkforward_run_id</div>
        <Link href={`/walkforward/${result.walkforward_run_id}`}>{result.walkforward_run_id}</Link>
      </div>
      <div className="grid two">
        <div className="card">
          <div className="small">Segments</div>
          <strong>{result.summary.segment_count}</strong>
        </div>
        <div className="card">
          <div className="small">총 Net 수익률</div>
          <strong>{result.summary.total_net_return_pct.toFixed(2)}%</strong>
        </div>
        <div className="card">
          <div className="small">평균 Segment 수익률</div>
          <strong>{result.summary.average_segment_return_pct.toFixed(2)}%</strong>
        </div>
        <div className="card">
          <div className="small">Benchmark 초과</div>
          <strong>{result.diagnostics.segments_beating_benchmark}</strong>
        </div>
      </div>
    </div>
  );
}
