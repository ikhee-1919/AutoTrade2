"use client";

import { useEffect, useMemo, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { StrategyParamsForm } from "@/components/strategy-params-form";
import { api } from "@/lib/api";
import { StrategyDetail, StrategyMeta } from "@/types/api";

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [strategyId, setStrategyId] = useState<string>("");
  const [detail, setDetail] = useState<StrategyDetail | null>(null);
  const [params, setParams] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const list = await api.listStrategies();
        setStrategies(list);
        if (list[0]) {
          setStrategyId(list[0].strategy_id);
        }
      } catch {
        setStrategies([]);
      }
    }
    init();
  }, []);

  useEffect(() => {
    async function load() {
      if (!strategyId) return;
      try {
        const [strategyDetail, strategyParams] = await Promise.all([
          api.getStrategy(strategyId),
          api.getStrategyParams(strategyId),
        ]);
        setDetail(strategyDetail);
        setParams(strategyParams.params);
      } catch {
        setDetail(null);
        setParams(null);
      }
    }
    load();
  }, [strategyId]);

  const hasData = useMemo(() => Boolean(detail && params), [detail, params]);

  return (
    <div>
      <h1>전략 설정</h1>
      <SectionCard title="전략 선택" description="코드로 등록된 전략 중에서 설정 대상을 선택합니다.">
        <select value={strategyId} onChange={(e) => setStrategyId(e.target.value)}>
          {strategies.map((s) => (
            <option key={s.strategy_id} value={s.strategy_id}>
              {s.name} ({s.version})
            </option>
          ))}
        </select>
      </SectionCard>

      <SectionCard title="전략 설명" description="전략 버전과 기본 설명">
        {detail ? (
          <div>
            <p>
              <strong>{detail.name}</strong> ({detail.version})
            </p>
            <p className="small">{detail.description}</p>
            <p className="small">mode: {detail.mode ?? "single_timeframe"}</p>
            <p className="small">
              required roles: {detail.required_roles?.join(", ") || "-"}
            </p>
            <p className="small">
              default mapping:{" "}
              {detail.default_timeframe_mapping
                ? Object.entries(detail.default_timeframe_mapping)
                    .map(([role, tf]) => `${role}:${tf}`)
                    .join(", ")
                : "-"}
            </p>
          </div>
        ) : (
          <div className="placeholder">전략 상세 정보를 불러오지 못했습니다.</div>
        )}
      </SectionCard>

      <SectionCard title="파라미터 수정" description="안전한 범위 내에서 숫자 파라미터만 수정합니다.">
        {hasData && params ? (
          <StrategyParamsForm strategyId={strategyId} initialParams={params} />
        ) : (
          <div className="placeholder">파라미터를 불러오는 중입니다.</div>
        )}
      </SectionCard>
    </div>
  );
}
