"use client";

import { useEffect, useMemo, useState } from "react";

import { ChartControls } from "@/components/chart/chart-controls";
import { MarketAnalysisChart } from "@/components/chart/market-analysis-chart";
import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import {
  ChartBacktestOverlayResponse,
  ChartCandlesResponse,
  ChartIndicatorsResponse,
  RecentBacktestItem,
} from "@/types/api";

const DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "60m", "240m", "1d"];

export default function ChartsPage() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [timeframes, setTimeframes] = useState<string[]>(DEFAULT_TIMEFRAMES);
  const [runs, setRuns] = useState<RecentBacktestItem[]>([]);

  const [symbol, setSymbol] = useState("KRW-BTC");
  const [timeframe, setTimeframe] = useState("1d");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [runId, setRunId] = useState("");

  const [candles, setCandles] = useState<ChartCandlesResponse | null>(null);
  const [indicators, setIndicators] = useState<ChartIndicatorsResponse | null>(null);
  const [overlay, setOverlay] = useState<ChartBacktestOverlayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [toggles, setToggles] = useState({
    ema20: true,
    ema50: true,
    ema120: true,
    rsi14: true,
    volume: true,
  });

  useEffect(() => {
    async function bootstrap() {
      try {
        const [summary, history] = await Promise.all([
          api.getMarketDataSummary(),
          api.listBacktestHistory(30),
        ]);
        const tf = summary.available_timeframes.length > 0 ? summary.available_timeframes : DEFAULT_TIMEFRAMES;
        setTimeframes(tf);
        setSymbols(summary.available_symbols.length > 0 ? summary.available_symbols : ["KRW-BTC"]);
        if (summary.available_symbols[0]) {
          setSymbol(summary.available_symbols[0]);
        }
        if (tf[0]) {
          setTimeframe(tf[0]);
        }
        setRuns(history);
      } catch {
        setSymbols(["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"]);
      }
    }
    void bootstrap();
  }, []);

  const loadChart = async () => {
    setLoading(true);
    setError(null);
    try {
      const indicatorKeys = [
        ...(toggles.ema20 ? ["ema20"] : []),
        ...(toggles.ema50 ? ["ema50"] : []),
        ...(toggles.ema120 ? ["ema120"] : []),
        ...(toggles.rsi14 ? ["rsi14"] : []),
        ...(toggles.volume ? ["volume_ma20"] : []),
      ];
      const [c, i, o] = await Promise.all([
        api.getChartCandles({ symbol, timeframe, start_date: startDate, end_date: endDate }),
        api.getChartIndicators({
          symbol,
          timeframe,
          start_date: startDate,
          end_date: endDate,
          indicators: indicatorKeys,
        }),
        runId ? api.getBacktestOverlay(runId) : Promise.resolve(null),
      ]);
      setCandles(c);
      setIndicators(i);
      setOverlay(o);
    } catch (e) {
      setError(e instanceof Error ? e.message : "차트 조회 실패");
      setCandles(null);
      setIndicators(null);
      setOverlay(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (symbols.length > 0) {
      void loadChart();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, timeframe, startDate, endDate]);

  const runOptions = useMemo(
    () =>
      runs.map((run) => ({
        run_id: run.run_id,
        label: `${run.strategy_id} / ${run.symbol} / ${run.timeframe} / ${new Date(run.run_at).toLocaleString()}`,
      })),
    [runs],
  );

  const mappingText = useMemo(() => {
    if (!overlay?.run_meta.timeframe_mapping) return "-";
    return Object.entries(overlay.run_meta.timeframe_mapping)
      .map(([role, tf]) => `${role}:${tf}`)
      .join(", ");
  }, [overlay]);

  return (
    <div>
      <h1>차트 분석 워크스페이스</h1>
      <SectionCard title="분석 조건" description="데이터셋 조회 + 지표 토글 + 백테스트 오버레이">
        <ChartControls
          symbols={symbols}
          timeframes={timeframes}
          runs={runOptions}
          symbol={symbol}
          timeframe={timeframe}
          startDate={startDate}
          endDate={endDate}
          runId={runId}
          indicators={toggles}
          onChange={(next) => {
            if (next.symbol !== undefined) setSymbol(next.symbol);
            if (next.timeframe !== undefined) setTimeframe(next.timeframe);
            if (next.startDate !== undefined) setStartDate(next.startDate);
            if (next.endDate !== undefined) setEndDate(next.endDate);
            if (next.runId !== undefined) setRunId(next.runId);
            if (next.indicators !== undefined) setToggles(next.indicators);
          }}
          onSubmit={() => void loadChart()}
        />
      </SectionCard>

      <SectionCard title="차트" description="캔들 + 이평선 + 거래량 + RSI + 매수/매도 오버레이">
        {error ? <p className="error">{error}</p> : null}
        {loading ? <div className="placeholder">차트 로딩 중...</div> : null}
        {candles && indicators ? (
          <div className="grid">
            <div className="card" style={{ marginBottom: 0 }}>
              <div className="small">
                source={candles.dataset?.source_type ?? "unknown"} / dataset={candles.dataset?.dataset_id ?? "-"} /
                quality={candles.dataset?.quality_status ?? "-"}
              </div>
              {overlay ? (
                <div className="small">
                  run={overlay.run_id} / strategy={overlay.run_meta.strategy_id} v{overlay.run_meta.strategy_version} /
                  code={overlay.run_meta.code_version} / timeframe_mapping={mappingText}
                </div>
              ) : null}
            </div>
            <MarketAnalysisChart candles={candles.items} indicators={indicators.items} overlay={overlay} toggles={toggles} />
          </div>
        ) : null}
      </SectionCard>

      {overlay ? (
        <SectionCard title="오버레이 거래 요약" description="차트 마커와 연결된 진입/청산 로그">
          {overlay.trades.length === 0 ? (
            <div className="placeholder">해당 run에 거래 로그가 없습니다.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>진입</th>
                  <th>청산</th>
                  <th>진입가</th>
                  <th>청산가</th>
                  <th>Exit Reason</th>
                  <th>Gross%</th>
                  <th>Net%</th>
                </tr>
              </thead>
              <tbody>
                {overlay.trades.map((trade, idx) => (
                  <tr key={`${trade.entry_time}-${idx}`}>
                    <td>{new Date(trade.entry_time).toLocaleString()}</td>
                    <td>{new Date(trade.exit_time).toLocaleString()}</td>
                    <td>{trade.entry_price.toLocaleString()}</td>
                    <td>{trade.exit_price.toLocaleString()}</td>
                    <td>{trade.exit_reason}</td>
                    <td>{trade.gross_pct.toFixed(2)}</td>
                    <td>{trade.net_pct.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>
      ) : null}
    </div>
  );
}
