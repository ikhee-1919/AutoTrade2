def test_regime_analyze_api(api_client) -> None:
    response = api_client.get(
        "/regime/analyze",
        params={
            "symbol": "BTC-KRW",
            "indicator_start": "2025-01-01",
            "analysis_start": "2025-06-01",
            "analysis_end": "2025-09-30",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "BTC-KRW"
    assert "regime_counts" in body
    assert "daily_points" in body
    assert "regime_segments" in body
    assert "above_200_segments" in body
    assert "below_200_segments" in body


def test_regime_analyze_batch_api(api_client) -> None:
    response = api_client.get(
        "/regime/analyze/batch",
        params=[
            ("symbols", "BTC-KRW"),
            ("symbols", "ETH-KRW"),
            ("indicator_start", "2025-01-01"),
            ("analysis_start", "2025-06-01"),
            ("analysis_end", "2025-09-30"),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert "summary" in body
    assert body["summary"]["symbol_count"] == 2
