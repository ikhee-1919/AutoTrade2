"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";
import { MarketDataDetail, MarketDataPreview } from "@/types/api";

export default function MarketDataDetailPage() {
  const params = useParams<{ dataset_id: string }>();
  const datasetId = decodeURIComponent(params.dataset_id);
  const [detail, setDetail] = useState<MarketDataDetail | null>(null);
  const [preview, setPreview] = useState<MarketDataPreview | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    const [d, p] = await Promise.all([
      api.getMarketDataset(datasetId),
      api.previewMarketDataset(datasetId, 20, true),
    ]);
    setDetail(d);
    setPreview(p);
  };

  useEffect(() => {
    void load();
  }, [datasetId]);

  const validateNow = async () => {
    try {
      const response = await api.validateMarketDataset(datasetId, false);
      setMessage(
        response.mode === "job"
          ? `검증 job 등록: ${response.job_id}`
          : `검증 완료: ${response.result?.quality_status ?? ""}`,
      );
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "검증 실패");
    }
  };

  if (!detail) {
    return <div className="placeholder">데이터셋 상세 로딩 중...</div>;
  }

  const q = detail.quality_report;
  return (
    <div>
      <h1>데이터셋 상세</h1>
      <p className="small">dataset_id: {datasetId}</p>
      <SectionCard title="Manifest" description="데이터셋 메타데이터">
        <table>
          <tbody>
            <tr>
              <th>source</th>
              <td>{detail.manifest.source}</td>
            </tr>
            <tr>
              <th>symbol/timeframe</th>
              <td>
                {detail.manifest.symbol} / {detail.manifest.timeframe}
              </td>
            </tr>
            <tr>
              <th>range</th>
              <td>
                {detail.manifest.start_at ?? "-"} ~ {detail.manifest.end_at ?? "-"}
              </td>
            </tr>
            <tr>
              <th>row_count</th>
              <td>{detail.manifest.row_count}</td>
            </tr>
            <tr>
              <th>quality_status</th>
              <td>{detail.manifest.quality_status}</td>
            </tr>
            <tr>
              <th>data_signature</th>
              <td>{detail.manifest.data_signature}</td>
            </tr>
            <tr>
              <th>path</th>
              <td>{detail.manifest.path}</td>
            </tr>
          </tbody>
        </table>
      </SectionCard>

      <SectionCard title="Quality Report" description="결측/중복/간격/OHLC 무결성 점검">
        <div className="grid two">
          <div className="card">
            <div className="small">status</div>
            <strong>{q.status}</strong>
          </div>
          <div className="card">
            <div className="small">row_count</div>
            <strong>{q.row_count}</strong>
          </div>
          <div className="card">
            <div className="small">duplicate_count</div>
            <strong>{q.duplicate_count}</strong>
          </div>
          <div className="card">
            <div className="small">missing_interval_count</div>
            <strong>{q.missing_interval_count}</strong>
          </div>
          <div className="card">
            <div className="small">null_count</div>
            <strong>{q.null_count}</strong>
          </div>
          <div className="card">
            <div className="small">invalid_ohlc_count</div>
            <strong>{q.invalid_ohlc_count}</strong>
          </div>
          <div className="card">
            <div className="small">suspicious_gap_count</div>
            <strong>{q.suspicious_gap_count}</strong>
          </div>
        </div>
        <p className="small">{q.summary_message}</p>
        {q.detail_messages.length > 0 ? (
          <ul>
            {q.detail_messages.map((msg, idx) => (
              <li key={`${idx}-${msg}`}>{msg}</li>
            ))}
          </ul>
        ) : null}
        <button type="button" onClick={() => void validateNow()}>
          validate 재실행
        </button>
        {message ? <p className="small">{message}</p> : null}
      </SectionCard>

      <SectionCard title="Preview" description="최근 샘플 행">
        {!preview || preview.rows.length === 0 ? (
          <div className="placeholder">미리보기 데이터가 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>timestamp</th>
                <th>open</th>
                <th>high</th>
                <th>low</th>
                <th>close</th>
                <th>volume</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row) => (
                <tr key={row.timestamp}>
                  <td>{row.timestamp}</td>
                  <td>{row.open}</td>
                  <td>{row.high}</td>
                  <td>{row.low}</td>
                  <td>{row.close}</td>
                  <td>{row.volume}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <Link href="/market-data">데이터 관리 목록으로 돌아가기</Link>
    </div>
  );
}
