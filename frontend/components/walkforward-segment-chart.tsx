import { WalkforwardSegment } from "@/types/api";

type WalkforwardSegmentChartProps = {
  segments: WalkforwardSegment[];
};

export function WalkforwardSegmentChart({ segments }: WalkforwardSegmentChartProps) {
  if (segments.length === 0) {
    return <div className="placeholder">세그먼트 데이터가 없습니다.</div>;
  }
  const maxAbs = Math.max(1, ...segments.map((s) => Math.abs(s.net_return_pct)));

  return (
    <div className="card">
      {segments.map((seg) => {
        const pct = (Math.abs(seg.net_return_pct) / maxAbs) * 100;
        const positive = seg.net_return_pct >= 0;
        const beatBenchmark = seg.excess_return_pct > 0;
        return (
          <div key={seg.segment_index} style={{ marginBottom: 10 }}>
            <div className="small">
              #{seg.segment_index} | {seg.test_start} ~ {seg.test_end} | net {seg.net_return_pct.toFixed(2)}%
              {beatBenchmark ? " | benchmark 상회" : " | benchmark 하회"}
            </div>
            <div className="progress-wrap">
              <div
                className="progress-fill"
                style={{
                  width: `${pct}%`,
                  background: positive ? "#10b981" : "#ef4444",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
