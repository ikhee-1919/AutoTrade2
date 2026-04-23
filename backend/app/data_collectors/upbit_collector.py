from datetime import date, datetime, timedelta
import time
from typing import Callable

import httpx

from app.data_collectors.base import HistoricalCandleCollector
from app.models.candle import Candle


class UpbitHistoricalCollector(HistoricalCandleCollector):
    def __init__(self, base_url: str = "https://api.upbit.com", timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
        progress_callback: Callable[[float], None] | None = None,
    ) -> list[Candle]:
        if start_date > end_date:
            raise ValueError("start_date must be earlier than or equal to end_date")

        path = self._candle_path(timeframe)
        cursor = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        unique: dict[str, Candle] = {}
        rounds = 0
        max_rounds = 3000

        with httpx.Client(timeout=self._timeout_seconds, headers={"User-Agent": "trading-console/0.1"}) as client:
            while rounds < max_rounds:
                rounds += 1
                batch = self._request_batch(client, path, symbol=symbol, cursor=cursor, count=200)
                if not batch:
                    break

                oldest_ts: datetime | None = None
                newest_ts: datetime | None = None
                for row in batch:
                    ts = datetime.fromisoformat(row["candle_date_time_utc"])
                    if newest_ts is None or ts > newest_ts:
                        newest_ts = ts
                    if oldest_ts is None or ts < oldest_ts:
                        oldest_ts = ts
                    day = ts.date()
                    if day < start_date or day > end_date:
                        continue
                    candle = Candle(
                        timestamp=ts,
                        open=float(row["opening_price"]),
                        high=float(row["high_price"]),
                        low=float(row["low_price"]),
                        close=float(row["trade_price"]),
                        volume=float(row.get("candle_acc_trade_volume", 0.0)),
                    )
                    unique[candle.timestamp.isoformat()] = candle

                if oldest_ts is None:
                    break

                if progress_callback and newest_ts and oldest_ts:
                    span_total = max((end_date - start_date).days + 1, 1)
                    covered = max((end_date - oldest_ts.date()).days + 1, 1)
                    progress_callback(min(95.0, (covered / span_total) * 100.0))

                if oldest_ts.date() <= start_date:
                    break
                cursor = oldest_ts - timedelta(seconds=1)
                time.sleep(0.03)

        candles = sorted(unique.values(), key=lambda c: c.timestamp)
        return candles

    def _request_batch(
        self,
        client: httpx.Client,
        path: str,
        symbol: str,
        cursor: datetime,
        count: int,
    ) -> list[dict]:
        url = f"{self._base_url}{path}"
        params = {
            "market": symbol,
            "count": min(max(count, 1), 200),
            "to": cursor.isoformat(timespec="seconds"),
        }
        retry = 0
        while retry < 3:
            retry += 1
            response = client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(0.25 * retry)
                continue
            raise ValueError(f"upbit collect failed: status={response.status_code}, body={response.text[:200]}")
        raise ValueError("upbit collect failed after retries")

    def _candle_path(self, timeframe: str) -> str:
        timeframe = {"1h": "60m", "4h": "240m"}.get(timeframe, timeframe)
        if timeframe == "1d":
            return "/v1/candles/days"
        if timeframe.endswith("m"):
            unit = timeframe[:-1]
            if unit not in {"1", "3", "5", "10", "15", "30", "60", "240"}:
                raise ValueError(f"unsupported minute timeframe: {timeframe}")
            return f"/v1/candles/minutes/{unit}"
        raise ValueError(f"unsupported timeframe: {timeframe}")
