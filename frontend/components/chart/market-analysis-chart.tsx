"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { EChartsOption } from "echarts";

import { ChartBacktestOverlayResponse, ChartCandleItem, ChartIndicatorItem } from "@/types/api";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type IndicatorToggles = {
  ema20: boolean;
  ema50: boolean;
  ema120: boolean;
  rsi14: boolean;
  volume: boolean;
};

type MarketAnalysisChartProps = {
  candles: ChartCandleItem[];
  indicators: ChartIndicatorItem[];
  toggles: IndicatorToggles;
  overlay?: ChartBacktestOverlayResponse | null;
  height?: number;
};

export function MarketAnalysisChart({ candles, indicators, toggles, overlay, height = 760 }: MarketAnalysisChartProps) {
  const option = useMemo<EChartsOption | null>(() => {
    if (!candles.length) return null;

    const times = candles.map((c) => c.time);
    const k = candles.map((c) => [c.open, c.close, c.low, c.high]);
    const volumes = candles.map((c, idx) => ({
      value: c.volume,
      itemStyle: { color: c.close >= c.open ? "#16a34a" : "#dc2626" },
      tooltip: { valueFormatter: (v: number) => v.toLocaleString() },
      idx,
    }));

    const byTime = new Map(indicators.map((item) => [item.time, item]));
    const ema20 = times.map((t) => byTime.get(t)?.ema20 ?? null);
    const ema50 = times.map((t) => byTime.get(t)?.ema50 ?? null);
    const ema120 = times.map((t) => byTime.get(t)?.ema120 ?? null);
    const rsi14 = times.map((t) => byTime.get(t)?.rsi14 ?? null);

    const entryMarkers = (overlay?.trades ?? []).map((trade) => ({
      value: [trade.entry_time, trade.entry_price],
      name: "BUY",
      itemStyle: { color: "#16a34a" },
      tooltip: {
        formatter: `진입<br/>${new Date(trade.entry_time).toLocaleString()}<br/>${trade.entry_price.toLocaleString()}`,
      },
    }));

    const exitMarkers = (overlay?.trades ?? []).map((trade) => ({
      value: [trade.exit_time, trade.exit_price],
      name: "SELL",
      itemStyle: { color: "#dc2626" },
      tooltip: {
        formatter: `청산<br/>${new Date(trade.exit_time).toLocaleString()}<br/>${trade.exit_price.toLocaleString()}<br/>${trade.exit_reason}<br/>Gross ${trade.gross_pct.toFixed(2)}% / Net ${trade.net_pct.toFixed(2)}%`,
      },
    }));

    const series: any[] = [
      { type: "candlestick", name: "Candles", data: k },
    ];

    if (toggles.ema20) {
      series.push({
        type: "line",
        name: "EMA20",
        data: ema20,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.4, color: "#2563eb" },
        emphasis: { disabled: true },
        silent: true,
      });
    }
    if (toggles.ema50) {
      series.push({
        type: "line",
        name: "EMA50",
        data: ema50,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.2, color: "#f59e0b" },
        emphasis: { disabled: true },
        silent: true,
      });
    }
    if (toggles.ema120) {
      series.push({
        type: "line",
        name: "EMA120",
        data: ema120,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.2, color: "#7c3aed" },
        emphasis: { disabled: true },
        silent: true,
      });
    }
    if (toggles.volume) {
      series.push({
        type: "bar",
        name: "Volume",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
      });
    }
    if (toggles.rsi14) {
      series.push({
        type: "line",
        name: "RSI14",
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: rsi14,
        showSymbol: false,
        lineStyle: { width: 1.6, color: "#0891b2" },
      });
    }
    series.push({
      type: "scatter",
      name: "Buy",
      symbol: "triangle",
      symbolRotate: 0,
      symbolSize: 11,
      data: entryMarkers,
    });
    series.push({
      type: "scatter",
      name: "Sell",
      symbol: "triangle",
      symbolRotate: 180,
      symbolSize: 11,
      data: exitMarkers,
    });

    return {
      animation: false,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
      },
      legend: {
        top: 6,
        data: ["Candles", "EMA20", "EMA50", "EMA120", "Volume", "RSI14", "Buy", "Sell"],
      },
      axisPointer: {
        link: [{ xAxisIndex: [0, 1, 2] }],
      },
      grid: [
        { left: 56, right: 24, top: 40, height: "52%" },
        { left: 56, right: 24, top: "64%", height: "14%" },
        { left: 56, right: 24, top: "82%", height: "14%" },
      ],
      xAxis: [
        { type: "category", data: times, boundaryGap: false, axisLine: { onZero: false } },
        { type: "category", gridIndex: 1, data: times, boundaryGap: false, axisLabel: { show: false } },
        { type: "category", gridIndex: 2, data: times, boundaryGap: false },
      ],
      yAxis: [
        { scale: true, splitArea: { show: true } },
        { scale: true, gridIndex: 1, splitNumber: 2 },
        { min: 0, max: 100, gridIndex: 2 },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1, 2], start: 0, end: 100 },
        { type: "slider", xAxisIndex: [0, 1, 2], top: "97%", start: 0, end: 100 },
      ],
      series,
    };
  }, [candles, indicators, overlay, toggles]);

  if (!option) {
    return <div className="placeholder">차트를 표시할 캔들 데이터가 없습니다.</div>;
  }

  return <ReactECharts option={option} style={{ width: "100%", height }} notMerge lazyUpdate />;
}
