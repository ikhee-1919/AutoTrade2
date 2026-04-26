from __future__ import annotations

from dataclasses import dataclass
import time

import httpx


@dataclass(frozen=True)
class RankedCoin:
    coin_id: str
    symbol: str
    name: str
    market_cap: float
    rank: int | None = None


class CoinGeckoMarketCapProvider:
    def __init__(self, base_url: str = "https://api.coingecko.com/api/v3", timeout_seconds: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_ranked_coins(self, max_items: int = 400) -> list[RankedCoin]:
        per_page = 250
        total_pages = max(1, (max_items + per_page - 1) // per_page)
        out: list[RankedCoin] = []

        with httpx.Client(timeout=self._timeout_seconds, headers={"User-Agent": "trading-console/0.1"}) as client:
            for page in range(1, total_pages + 1):
                if len(out) >= max_items:
                    break
                rows = self._request_markets_page(client, page=page, per_page=per_page)
                if not rows:
                    break
                for row in rows:
                    market_cap = float(row.get("market_cap") or 0.0)
                    if market_cap <= 0:
                        continue
                    out.append(
                        RankedCoin(
                            coin_id=str(row.get("id", "")),
                            symbol=str(row.get("symbol", "")).upper(),
                            name=str(row.get("name", "")),
                            market_cap=market_cap,
                            rank=int(row.get("market_cap_rank")) if row.get("market_cap_rank") is not None else None,
                        )
                    )
                time.sleep(0.08)

        out.sort(key=lambda item: item.market_cap, reverse=True)
        return out[:max_items]

    def _request_markets_page(self, client: httpx.Client, page: int, per_page: int) -> list[dict]:
        url = f"{self._base_url}/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }

        for retry in range(1, 4):
            res = client.get(url, params=params)
            if res.status_code == 200:
                return res.json()
            if res.status_code in {429, 500, 502, 503, 504}:
                time.sleep(0.2 * retry)
                continue
            raise ValueError(f"coingecko request failed: status={res.status_code}, body={res.text[:200]}")
        raise ValueError("coingecko request failed after retries")
