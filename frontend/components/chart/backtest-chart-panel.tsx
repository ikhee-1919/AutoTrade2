"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import {
  ChartBacktestOverlayResponse,
  ChartCandlesResponse,
  ChartIndicatorsResponse,
} from "@/types/api";
import { MarketAnalysisChart } from "@/components/chart/market-analysis-chart";

type BacktestChartPanelProps = {
  runId: string;
  symbol: string;
  timeframe: string;
  startDate: string;
  endDate: string;
};

export function BacktestChartPanel({ runId, symbol, timeframe, startDate, endDate }: BacktestChartPanelProps) {
  const [candles, setCandles] = useState<ChartCandlesResponse | null>(null);
  const [indicators, setIndicators] = useState<ChartIndicatorsResponse | null>(null);
  const [overlay, setOverlay] = useState<ChartBacktestOverlayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setError(null);
      try {
        const [c, i, o] = await Promise.all([
          api.getChartCandles({ symbol, timeframe, start_date: startDate, end_date: endDate }),
          api.getChartIndicators({
            symbol,
            timeframe,
            start_date: startDate,
            end_date: endDate,
            indicators: ["ema20", "ema50", "ema120", "rsi14", "volume_ma20"],
          }),
          api.getBacktestOverlay(runId),
        ]);
        setCandles(c);
        setIndicators(i);
        setOverlay(o);
      } catch (e) {
        setError(e instanceof Error ? e.message : "차트를 불러오지 못했습니다.");
      }
    }
    void load();
  }, [endDate, runId, startDate, symbol, timeframe]);

  const mappingText = useMemo(() => {
    if (!overlay?.run_meta.timeframe_mapping) return "-";
    return Object.entries(overlay.run_meta.timeframe_mapping)
      .map(([role, tf]) => `${role}:${tf}`)
      .join(", ");
  }, [overlay]);

  if (error) {
    return <p className="error">{error}</p>;
  }
  if (!candles || !indicators) {
    return <div className="placeholder">차트 로딩 중...</div>;
  }

  return (
    <div className="grid">
      <div className="card" style={{ marginBottom: 0 }}>
        <div className="small">
          dataset={candles.dataset?.source_type ?? "unknown"} / id={candles.dataset?.dataset_id ?? "-"} / quality={
            candles.dataset?.quality_status ?? "-"
          }
        </div>
        <div className="small">timeframe_mapping={mappingText}</div>
      </div>
      <MarketAnalysisChart
        candles={candles.items}
        indicators={indicators.items}
        overlay={overlay}
        toggles={{ ema20: true, ema50: true, ema120: true, rsi14: true, volume: true }}
      />
    </div>
  );
}
