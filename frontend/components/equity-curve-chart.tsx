type EquityPoint = {
  timestamp: string;
  equity: number;
};

type EquityCurveChartProps = {
  points: EquityPoint[];
  benchmarkPoints?: EquityPoint[];
  height?: number;
};

export function EquityCurveChart({ points, benchmarkPoints = [], height = 240 }: EquityCurveChartProps) {
  if (points.length < 2) {
    return <div className="placeholder">자산곡선을 표시할 데이터가 부족합니다.</div>;
  }

  const width = 900;
  const combined = [...points, ...benchmarkPoints];
  const min = Math.min(...combined.map((p) => p.equity));
  const max = Math.max(...combined.map((p) => p.equity));
  const range = Math.max(max - min, 0.000001);

  const path = points
    .map((point, idx) => {
      const x = (idx / (points.length - 1)) * width;
      const y = height - ((point.equity - min) / range) * height;
      return `${idx === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  const benchmarkPath =
    benchmarkPoints.length < 2
      ? null
      : benchmarkPoints
          .map((point, idx) => {
            const x = (idx / (benchmarkPoints.length - 1)) * width;
            const y = height - ((point.equity - min) / range) * height;
            return `${idx === 0 ? "M" : "L"}${x},${y}`;
          })
          .join(" ");

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="equity curve">
      <rect x="0" y="0" width={width} height={height} fill="#ffffff" />
      {benchmarkPath ? (
        <path d={benchmarkPath} fill="none" stroke="#9ca3af" strokeWidth="2" strokeDasharray="4 3" />
      ) : null}
      <path d={path} fill="none" stroke="#1d4ed8" strokeWidth="2" />
    </svg>
  );
}
