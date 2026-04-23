type Point = {
  timestamp: string;
  close: number;
};

type SimplePriceChartProps = {
  points: Point[];
  height?: number;
};

export function SimplePriceChart({ points, height = 240 }: SimplePriceChartProps) {
  if (points.length < 2) {
    return <div className="placeholder">차트를 표시할 데이터가 부족합니다.</div>;
  }

  const width = 900;
  const minPrice = Math.min(...points.map((p) => p.close));
  const maxPrice = Math.max(...points.map((p) => p.close));
  const range = Math.max(maxPrice - minPrice, 1);

  const path = points
    .map((point, idx) => {
      const x = (idx / (points.length - 1)) * width;
      const y = height - ((point.close - minPrice) / range) * height;
      return `${idx === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="price chart">
      <rect x="0" y="0" width={width} height={height} fill="#ffffff" />
      <path d={path} fill="none" stroke="#0f766e" strokeWidth="2" />
    </svg>
  );
}
