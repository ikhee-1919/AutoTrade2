"use client";

type IndicatorToggles = {
  ema20: boolean;
  ema50: boolean;
  ema120: boolean;
  rsi14: boolean;
  volume: boolean;
};

type ChartControlsProps = {
  symbols: string[];
  timeframes: string[];
  runs: Array<{ run_id: string; label: string }>;
  symbol: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  runId: string;
  indicators: IndicatorToggles;
  onChange: (next: {
    symbol?: string;
    timeframe?: string;
    startDate?: string;
    endDate?: string;
    runId?: string;
    indicators?: IndicatorToggles;
  }) => void;
  onSubmit: () => void;
};

export function ChartControls({
  symbols,
  timeframes,
  runs,
  symbol,
  timeframe,
  startDate,
  endDate,
  runId,
  indicators,
  onChange,
  onSubmit,
}: ChartControlsProps) {
  return (
    <div className="grid two">
      <div>
        <label>종목</label>
        <select value={symbol} onChange={(e) => onChange({ symbol: e.target.value })}>
          {symbols.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label>타임프레임</label>
        <select value={timeframe} onChange={(e) => onChange({ timeframe: e.target.value })}>
          {timeframes.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label>시작일</label>
        <input type="date" value={startDate} onChange={(e) => onChange({ startDate: e.target.value })} />
      </div>
      <div>
        <label>종료일</label>
        <input type="date" value={endDate} onChange={(e) => onChange({ endDate: e.target.value })} />
      </div>
      <div>
        <label>백테스트 run (선택)</label>
        <select value={runId} onChange={(e) => onChange({ runId: e.target.value })}>
          <option value="">없음</option>
          {runs.map((item) => (
            <option key={item.run_id} value={item.run_id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: "flex", alignItems: "end" }}>
        <button type="button" onClick={onSubmit}>
          차트 조회
        </button>
      </div>
      <div style={{ gridColumn: "1 / -1" }}>
        <label>지표 토글</label>
        <div className="chart-toggle-row">
          <label className="chart-toggle-item">
            <input
              type="checkbox"
              checked={indicators.ema20}
              onChange={(e) => onChange({ indicators: { ...indicators, ema20: e.target.checked } })}
            />
            EMA20
          </label>
          <label className="chart-toggle-item">
            <input
              type="checkbox"
              checked={indicators.ema50}
              onChange={(e) => onChange({ indicators: { ...indicators, ema50: e.target.checked } })}
            />
            EMA50
          </label>
          <label className="chart-toggle-item">
            <input
              type="checkbox"
              checked={indicators.ema120}
              onChange={(e) => onChange({ indicators: { ...indicators, ema120: e.target.checked } })}
            />
            EMA120
          </label>
          <label className="chart-toggle-item">
            <input
              type="checkbox"
              checked={indicators.rsi14}
              onChange={(e) => onChange({ indicators: { ...indicators, rsi14: e.target.checked } })}
            />
            RSI14
          </label>
          <label className="chart-toggle-item">
            <input
              type="checkbox"
              checked={indicators.volume}
              onChange={(e) => onChange({ indicators: { ...indicators, volume: e.target.checked } })}
            />
            Volume
          </label>
        </div>
      </div>
    </div>
  );
}
