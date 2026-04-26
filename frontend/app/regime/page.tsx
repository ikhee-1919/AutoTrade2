"use client";

import { useEffect, useMemo, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import { RegimeAnalyzeResponse, RegimeBatchAnalyzeResponse } from "@/types/api";

export default function RegimePage() {
  const [symbols, setSymbols] = useState<string[]>(["BTC-KRW", "ETH-KRW"]);
  const [symbol, setSymbol] = useState("BTC-KRW");
  const [indicatorStart, setIndicatorStart] = useState("2025-01-01");
  const [analysisStart, setAnalysisStart] = useState("2026-01-25");
  const [analysisEnd, setAnalysisEnd] = useState("2026-04-25");

  const [result, setResult] = useState<RegimeAnalyzeResponse | null>(null);
  const [batch, setBatch] = useState<RegimeBatchAnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function bootstrap() {
      try {
        const payload = await api.listSymbolsByTimeframe("1d");
        if (payload.symbols.length > 0) {
          setSymbols(payload.symbols);
          setSymbol(payload.symbols.includes("BTC-KRW") ? "BTC-KRW" : payload.symbols[0]);
        }
      } catch {
        // keep fallback
      }
    }
    void bootstrap();
  }, []);

  const runAnalyze = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.getRegimeAnalysis({
        symbol,
        indicator_start: indicatorStart,
        analysis_start: analysisStart,
        analysis_end: analysisEnd,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "레짐 분석 실패");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const runBatch = async () => {
    setError(null);
    setLoading(true);
    try {
      const targets = ["BTC-KRW", "ETH-KRW"].filter((s) => symbols.includes(s));
      const res = await api.getRegimeAnalysisBatch({
        symbols: targets.length > 0 ? targets : symbols.slice(0, 2),
        indicator_start: indicatorStart,
        analysis_start: analysisStart,
        analysis_end: analysisEnd,
      });
      setBatch(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "배치 레짐 분석 실패");
      setBatch(null);
    } finally {
      setLoading(false);
    }
  };

  const topRegimes = useMemo(() => {
    if (!result) return [] as [string, number][];
    return Object.entries(result.regime_counts).sort((a, b) => b[1] - a[1]);
  }, [result]);

  return (
    <div>
      <h1>시장 레짐 분석 (200일선)</h1>
      <SectionCard title="분석 조건" description="indicator_start(지표 계산 시작)와 분석 구간을 분리해 조회합니다.">
        <div className="grid two">
          <label>
            Symbol
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {symbols.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Indicator Start
            <input type="date" value={indicatorStart} onChange={(e) => setIndicatorStart(e.target.value)} />
          </label>
          <label>
            Analysis Start
            <input type="date" value={analysisStart} onChange={(e) => setAnalysisStart(e.target.value)} />
          </label>
          <label>
            Analysis End
            <input type="date" value={analysisEnd} onChange={(e) => setAnalysisEnd(e.target.value)} />
          </label>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <button type="button" onClick={() => void runAnalyze()} disabled={loading}>
            단일 종목 분석
          </button>
          <button type="button" onClick={() => void runBatch()} disabled={loading}>
            BTC/ETH 배치 분석
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </SectionCard>

      <SectionCard title="요약" description="200일선 위/아래 일수와 레짐 카운트 요약">
        {loading ? <div className="placeholder">분석 중...</div> : null}
        {result ? (
          <div className="grid three">
            <div className="card" style={{ marginBottom: 0 }}>
              <p>
                <strong>{result.symbol}</strong>
              </p>
              <p className="small">dataset: {result.dataset.dataset_id ?? "-"}</p>
              <p className="small">source: {result.dataset.source_type ?? "-"}</p>
            </div>
            <div className="card" style={{ marginBottom: 0 }}>
              <p>above_200_days: {result.above_200_days}</p>
              <p>below_200_days: {result.below_200_days}</p>
              <p>insufficient_history_days: {result.insufficient_history_days}</p>
            </div>
            <div className="card" style={{ marginBottom: 0 }}>
              <p>above_200_return: {result.above_200_return.toFixed(2)}%</p>
              <p>below_200_return: {result.below_200_return.toFixed(2)}%</p>
            </div>
          </div>
        ) : (
          <div className="placeholder">아직 분석 결과가 없습니다.</div>
        )}
      </SectionCard>

      {result ? (
        <SectionCard title="레짐 카운트" description="해당 분석 구간의 레짐 분포">
          {topRegimes.length === 0 ? (
            <div className="placeholder">레짐 카운트가 없습니다.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Regime</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {topRegimes.map(([label, value]) => (
                  <tr key={label}>
                    <td>{label}</td>
                    <td>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>
      ) : null}

      {result ? (
        <SectionCard title="SMA200 위/아래 연속 구간" description="연속 구간별 return, 거리, slope 상태">
          <div className="grid two">
            <div>
              <h3 style={{ marginTop: 0 }}>Above 200</h3>
              <table>
                <thead>
                  <tr>
                    <th>Start</th>
                    <th>End</th>
                    <th>Days</th>
                    <th>Return%</th>
                    <th>Slope</th>
                  </tr>
                </thead>
                <tbody>
                  {result.above_200_segments.map((seg) => (
                    <tr key={`${seg.start_date}-${seg.end_date}-above`}>
                      <td>{seg.start_date}</td>
                      <td>{seg.end_date}</td>
                      <td>{seg.days}</td>
                      <td>{seg.return_pct.toFixed(2)}</td>
                      <td>{seg.sma200_slope_state}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h3 style={{ marginTop: 0 }}>Below 200</h3>
              <table>
                <thead>
                  <tr>
                    <th>Start</th>
                    <th>End</th>
                    <th>Days</th>
                    <th>Return%</th>
                    <th>Slope</th>
                  </tr>
                </thead>
                <tbody>
                  {result.below_200_segments.map((seg) => (
                    <tr key={`${seg.start_date}-${seg.end_date}-below`}>
                      <td>{seg.start_date}</td>
                      <td>{seg.end_date}</td>
                      <td>{seg.days}</td>
                      <td>{seg.return_pct.toFixed(2)}</td>
                      <td>{seg.sma200_slope_state}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </SectionCard>
      ) : null}

      {batch ? (
        <SectionCard title="BTC/ETH 배치 요약" description="두 종목의 구간 레짐 집계를 한 번에 확인">
          <div className="grid two">
            {batch.items.map((item) => (
              <div key={item.symbol} className="card" style={{ marginBottom: 0 }}>
                <p>
                  <strong>{item.symbol}</strong>
                </p>
                <p className="small">above: {item.above_200_days} days</p>
                <p className="small">below: {item.below_200_days} days</p>
                <p className="small">insufficient: {item.insufficient_history_days} days</p>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}
