from app.strategy.registry import StrategyRegistry
from app.strategy.samples.mtf_confluence_pullback_v2 import MTFConfluencePullbackV2Strategy
from app.strategy.samples.mtf_confluence_pullback_v2_variants import BullAbove200LongV1LooserStrategy


def test_registry_contains_bull_looser_variant() -> None:
    ids = {s.metadata().strategy_id for s in StrategyRegistry().list()}
    assert "bull_above_200_long_v1_looser" in ids


def test_strategies_api_exposes_bull_looser_variant(api_client) -> None:
    response = api_client.get("/strategies")
    assert response.status_code == 200
    ids = {item["strategy_id"] for item in response.json()}
    assert "bull_above_200_long_v1_looser" in ids


def test_looser_variant_relaxes_trend_gate() -> None:
    base = MTFConfluencePullbackV2Strategy()
    looser = BullAbove200LongV1LooserStrategy()
    bp = base.default_params()
    lp = looser.default_params()
    assert bp["allow_trend_alt_gate"] is False
    assert lp["allow_trend_alt_gate"] is True
    assert lp["trend_structure_tolerance_pct"] > bp["trend_structure_tolerance_pct"]


def test_looser_variant_relaxes_setup_rsi_and_pullback() -> None:
    base = MTFConfluencePullbackV2Strategy()
    looser = BullAbove200LongV1LooserStrategy()
    bp = base.default_params()
    lp = looser.default_params()
    assert lp["setup_rsi_min"] < bp["setup_rsi_min"]
    assert lp["setup_rsi_max"] > bp["setup_rsi_max"]
    assert lp["setup_pullback_near_pct"] > bp["setup_pullback_near_pct"]
    assert lp["setup_lower_low_tolerance_pct"] > bp["setup_lower_low_tolerance_pct"]


def test_looser_variant_relaxes_trigger_reclaim_path() -> None:
    base = MTFConfluencePullbackV2Strategy()
    looser = BullAbove200LongV1LooserStrategy()
    bp = base.default_params()
    lp = looser.default_params()
    assert bp["require_local_high_break"] is True
    assert lp["require_local_high_break"] is False
    assert lp["allow_reclaim_bullish_without_high_break"] is True
    assert lp["entry_volume_multiplier"] < bp["entry_volume_multiplier"]
    assert lp["trigger_bullish_body_ratio_min"] < bp["trigger_bullish_body_ratio_min"]


def test_baseline_v2_defaults_unchanged() -> None:
    base = MTFConfluencePullbackV2Strategy().default_params()
    assert base["allow_trend_alt_gate"] is False
    assert base["setup_rsi_min"] == 40.0
    assert base["setup_rsi_max"] == 60.0
    assert base["require_local_high_break"] is True
    assert base["entry_volume_multiplier"] == 1.1
