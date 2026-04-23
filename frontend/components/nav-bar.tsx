import Link from "next/link";

export function NavBar() {
  return (
    <nav className="nav">
      <strong>Upbit Trading Console</strong>
      <Link href="/">대시보드</Link>
      <Link href="/backtests">백테스트</Link>
      <Link href="/sweeps">파라미터 스윕</Link>
      <Link href="/walkforward">Walk-Forward</Link>
      <Link href="/market-data">데이터 관리</Link>
      <Link href="/strategies">전략 설정</Link>
      <Link href="/signals">차트/시그널</Link>
    </nav>
  );
}
