"use client";

import { useEffect, useMemo, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { SimplePriceChart } from "@/components/simple-price-chart";
import { api } from "@/lib/api";
import { SignalResponse, StrategyMeta } from "@/types/api";

export default function SignalsPage() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [strategyId, setStrategyId] = useState<string>("");
  const [symbol, setSymbol] = useState<string>("");
  const [payload, setPayload] = useState<SignalResponse | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const [strategyData, symbolData] = await Promise.all([
          api.listStrategies(),
          api.listSymbols(),
        ]);
        setStrategies(strategyData);
        setSymbols(symbolData.symbols);
        if (strategyData[0]) setStrategyId(strategyData[0].strategy_id);
        if (symbolData.symbols[0]) setSymbol(symbolData.symbols[0]);
      } catch {
        setStrategies([]);
        setSymbols([]);
      }
    }
    init();
  }, []);

  useEffect(() => {
    async function loadSignals() {
      if (!strategyId || !symbol) return;
      try {
        const data = await api.getSignals(symbol, strategyId, "1d");
        setPayload(data);
      } catch {
        setPayload(null);
      }
    }
    loadSignals();
  }, [strategyId, symbol]);

  const latestSignals = useMemo(() => payload?.signals.slice(-15).reverse() ?? [], [payload]);

  return (
    <div>
      <h1>종목 차트/시그널</h1>
      <SectionCard title="조회 조건" description="종목과 전략을 선택해 최근 신호와 거절 사유를 확인합니다.">
        <div className="grid two">
          <div>
            <label>전략</label>
            <select value={strategyId} onChange={(e) => setStrategyId(e.target.value)}>
              {strategies.map((strategy) => (
                <option key={strategy.strategy_id} value={strategy.strategy_id}>
                  {strategy.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>종목</label>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {symbols.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="가격 시계열 (임시 차트)" description="향후 캔들/마커 차트 컴포넌트로 확장 가능한 자리입니다.">
        {payload ? <SimplePriceChart points={payload.prices} /> : <div className="placeholder">데이터 없음</div>}
      </SectionCard>

      <SectionCard title="최근 신호 및 거절 사유" description="entry_allowed=false 인 경우 reject_reason 확인 가능">
        {latestSignals.length === 0 ? (
          <div className="placeholder">표시할 시그널이 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>시각</th>
                <th>가격</th>
                <th>Regime</th>
                <th>Score</th>
                <th>진입 허용</th>
                <th>거절 사유</th>
              </tr>
            </thead>
            <tbody>
              {latestSignals.map((signal) => (
                <tr key={signal.timestamp}>
                  <td>{new Date(signal.timestamp).toLocaleString()}</td>
                  <td>{signal.price.toLocaleString()}</td>
                  <td>{signal.regime}</td>
                  <td>{signal.score.toFixed(2)}</td>
                  <td>{signal.entry_allowed ? "YES" : "NO"}</td>
                  <td>{signal.reject_reason ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>
    </div>
  );
}
