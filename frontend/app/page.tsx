import { SectionCard } from "@/components/section-card";
import { api } from "@/lib/api";

export default async function DashboardPage() {
  let strategies = [] as Awaited<ReturnType<typeof api.listStrategies>>;
  let recent = [] as Awaited<ReturnType<typeof api.listRecentBacktests>>;

  try {
    [strategies, recent] = await Promise.all([api.listStrategies(), api.listRecentBacktests()]);
  } catch {
    // Keep dashboard renderable even when backend is not running.
  }

  return (
    <div>
      <h1>Upbit 자동매매 운영 콘솔 (Backtest-First)</h1>
      <p className="small">
        전략 로직은 코드에서 관리하고, 웹에서는 상태 확인/백테스트/파라미터 관리만 수행합니다.
      </p>

      <div className="grid two">
        <SectionCard title="사용 가능한 전략" description="코드로 등록된 전략 버전 목록">
          {strategies.length === 0 ? (
            <div className="placeholder">전략 목록을 불러오지 못했습니다. 백엔드 실행 상태를 확인하세요.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>이름</th>
                  <th>버전</th>
                </tr>
              </thead>
              <tbody>
                {strategies.map((strategy) => (
                  <tr key={strategy.strategy_id}>
                    <td>{strategy.strategy_id}</td>
                    <td>{strategy.name}</td>
                    <td>{strategy.version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>

        <SectionCard title="최근 백테스트 요약" description="가장 최근 실행된 백테스트 결과">
          {recent[0] ? (
            <div>
              <p>
                <strong>{recent[0].strategy_id}</strong> / {recent[0].symbol} / {recent[0].timeframe}
              </p>
              <p>
                수익률 <span className="badge">{recent[0].total_return_pct.toFixed(2)}%</span>
              </p>
              <p className="small">거래 수: {recent[0].trade_count}</p>
            </div>
          ) : (
            <div className="placeholder">아직 백테스트 실행 이력이 없습니다.</div>
          )}
        </SectionCard>
      </div>

      <SectionCard title="향후 확장 영역" description="현재는 인터페이스만 준비">
        <div className="grid two">
          <div className="placeholder">Paper Trading Adapter (예정)</div>
          <div className="placeholder">Live Trading Adapter (예정)</div>
        </div>
      </SectionCard>
    </div>
  );
}
