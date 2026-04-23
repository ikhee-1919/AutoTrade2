"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";

type StrategyParamsFormProps = {
  strategyId: string;
  initialParams: Record<string, number>;
};

export function StrategyParamsForm({ strategyId, initialParams }: StrategyParamsFormProps) {
  const [params, setParams] = useState<Record<string, number>>(initialParams);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const keys = useMemo(() => Object.keys(params), [params]);

  const onChange = (key: string, value: string) => {
    setParams((prev) => ({ ...prev, [key]: Number(value) }));
  };

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const res = await api.updateStrategyParams(strategyId, params);
      setParams(res.params);
      setMessage("파라미터가 저장되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid two">
      {keys.map((key) => (
        <div key={key}>
          <label>{key}</label>
          <input
            type="number"
            value={params[key]}
            step="0.01"
            onChange={(e) => onChange(key, e.target.value)}
          />
        </div>
      ))}
      <div style={{ gridColumn: "1 / -1" }}>
        <button type="button" disabled={saving} onClick={save}>
          {saving ? "저장 중..." : "파라미터 저장"}
        </button>
        {message ? <p className="small">{message}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </div>
    </div>
  );
}
