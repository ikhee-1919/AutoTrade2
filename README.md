# Upbit Backtest Console (Research Console + Market Data Manager)

코드 기반 전략을 웹에서 운영/검증하는 콘솔입니다.  
현재는 백테스트 현실화 + walk-forward 분석 + 업비트 과거 데이터 수집/검증 관리까지 포함합니다.

## 핵심 원칙
- 전략 판단 로직은 코드(`backend/app/strategy`)에 유지
- 웹은 실행/비교/리포트/파라미터 운영 콘솔 역할
- 백테스트/향후 paper/live가 같은 전략 엔진 인터페이스 공유
- Docker 없이 로컬 실행 기준

## Tech Stack
- Frontend: Next.js + TypeScript
- Backend: FastAPI + Pydantic
- Storage: JSON file repository (향후 PostgreSQL 교체 가능 구조)
- Data:
  - sample CSV (`data/sample`)
  - collected market datasets (`data/market/upbit/{symbol}/{timeframe}`)

## 프로젝트 구조
```text
project-root/
  frontend/
    app/
    components/
    lib/
    types/
  backend/
    app/
      api/
      core/
      services/
      models/
      schemas/
      strategy/
      backtest/
      data/
      repositories/
      execution/
    tests/
  data/
    sample/
  docs/
  README.md
```

## 이번 단계에서 강화된 백테스트 현실화

### 1) 수수료 모델
- 매수/매도 각각 수수료 반영
- 설정:
  - `fee_rate`
  - `entry_fee_rate` / `exit_fee_rate` (없으면 `fee_rate` 사용)
  - `apply_fee_on_entry` / `apply_fee_on_exit`
- 거래 로그 필드:
  - `gross_pnl`, `net_pnl`
  - `fee_entry`, `fee_exit`, `total_fees`
- 요약 필드:
  - `gross_return_pct`, `net_return_pct`
  - `total_fees_paid`

### 2) 슬리피지 모델
- 고정 비율 슬리피지 반영(진입/청산 분리 가능)
- 설정:
  - `slippage_rate`
  - `entry_slippage_rate` / `exit_slippage_rate`
- 거래 로그 필드:
  - `intended_entry_price`, `filled_entry_price`
  - `intended_exit_price`, `filled_exit_price`
  - `slippage_entry_cost`, `slippage_exit_cost`, `total_slippage_cost`
- 요약 필드:
  - `total_slippage_cost`

### 3) 보수적 체결 정책 (`execution_policy`)
- `next_open` (기본): 신호 다음 봉 시가 체결
- `signal_close`: 신호 봉 종가 체결
- 실행 시 사용한 정책은 `execution_config`/`params_snapshot`/run metadata에 저장되어 rerun 재현 가능

### 4) Buy & Hold 벤치마크
- 동일 종목/동일 기간 기준 계산
- `benchmark` 필드:
  - `benchmark_buy_and_hold_return_pct`
  - `strategy_excess_return_pct`
  - `benchmark_start_price`, `benchmark_end_price`
  - `benchmark_curve`

### 5) 비용 영향 리포트
- 요약:
  - `total_trading_cost`
  - `cost_drag_pct` (gross - net)
  - `total_fees_paid`, `total_slippage_cost`
- 거래 단위:
  - `total_trading_cost`
  - gross vs net 비교 가능

## Walk-Forward 분석 골격

### Walk-Forward가 무엇인가
- 단일 기간 한 번의 백테스트가 아니라, 전체 기간을 여러 `train/test` 세그먼트로 나누어 반복 평가합니다.
- 이 프로젝트의 현재 구현은 `fixed-params walk-forward`입니다.
- 즉, in-sample 파라미터 최적화 엔진은 아직 구현하지 않고, 동일 파라미터를 순차 OOS(test) 구간에 적용합니다.

### 설정 의미
- `train_window_size`: 세그먼트의 학습/컨텍스트 길이
- `test_window_size`: out-of-sample 평가 길이
- `step_size`: 다음 세그먼트 이동 간격
- `window_unit`: `candles` 또는 `days` (현재 skeleton 단계에서는 candle-step 기반)
- `walkforward_mode`:
  - `rolling`: train window가 step마다 앞으로 이동
  - `anchored`: train 시작점을 고정하고 train 구간을 점진 확장
- `execution_config`(fee/slippage/execution_policy/benchmark): 기존 백테스트와 동일

### 결과 구조
- 메타데이터:
  - `walkforward_run_id`, `strategy_version`, `code_version`, `request_hash`, `params_snapshot`
- 세그먼트:
  - `train_start/end`, `test_start/end`, `linked_run_id`, `net_return_pct`, `max_drawdown`, `benchmark`, `excess_return`
- 전체 요약:
  - `total_net_return_pct`, `average_segment_return_pct`, `best/worst`, `average_max_drawdown`, `total_trade_count`
- 진단:
  - `profitable_segments`, `losing_segments`, `segments_beating_benchmark`
- 해석 문장:
  - rule-based `interpretation_summary`

## 멀티 타임프레임 전략 입력 매핑

### 개념
- 단일 `timeframe`만 받는 방식 대신 `timeframe_mapping`으로 role별 타임프레임을 명시합니다.
- 예시:
```json
{
  "timeframe_mapping": {
    "trend": "60m",
    "setup": "15m",
    "entry": "5m"
  }
}
```

### 현재 구현 상태
- strategy metadata에 `mode(single/multi)`와 `required_roles`가 노출됩니다.
- provider는 role별 dataset bundle을 한 번에 로드합니다.
- run metadata에 아래가 저장됩니다.
  - `timeframe_mapping`
  - `selected_datasets_by_role`
  - entry role 기준 `data_signature`
- 샘플 멀티 타임프레임 전략:
  - `mtf_trend_pullback_v1`
  - `mtf_trend_pullback_v2`

### 미래 데이터 누수 방지 원칙
- entry role의 현재 시점(`as_of`)을 기준으로 각 role(trend/setup/entry)은 `as_of` 이하로 확정된 봉만 사용합니다.
- 즉, 상위/중간 timeframe에서 아직 확정되지 않은 미래 봉은 참조하지 않습니다.
- 구현상 전략 컨텍스트 생성 시 role별 히스토리를 `timestamp <= as_of`로 잘라 전달합니다.

## 200일선 레짐 분류 + Warmup 처리

### 왜 hard filter만 쓰면 문제가 생기나
- `close < SMA200 => 무조건 거래 금지`만 쓰면, 전략 품질 문제와 데이터/지표 히스토리 부족 문제가 섞여 보입니다.
- 특히 `insufficient_regime_history`는 “약세장이라서 진입 거절”이 아니라, **SMA200을 계산할 충분한 일봉이 없어서 레짐 판정을 못 한 상태**를 의미합니다.

### 실행 구간 구분
- `indicator_start`(또는 `warmup_start`): 지표 계산용 과거 구간 시작점
- `trade_start`: 실제 성과 집계 시작점
- `trade_end`: 실제 성과 집계 종료점
- 엔진은 `indicator_start ~ trade_end`를 로드하고, 성과/거래 집계는 `trade_start ~ trade_end`만 반영합니다.

### MTF Walk-Forward role history 점검
- MTF 전략은 role마다 필요한 lookback이 다릅니다. 예: `regime(1d)`는 길고, `trigger(15m)`는 상대적으로 짧습니다.
- 따라서 `indicator_start`가 충분해도 세그먼트 실행 시 role별 slice가 짧으면 `insufficient_setup_history`가 발생할 수 있습니다.
- 현재 walk-forward 세그먼트 결과에는 아래 디버그 필드가 포함됩니다.
  - `role_history_counts`
  - `role_history_required`
  - `role_history_sufficient`
  - `role_history_missing_roles`
- 이 필드로 “전략 규칙 문제”와 “데이터/엔진 history 부족 문제”를 분리해서 해석할 수 있습니다.

### 4개 레짐 정의
- `bull_above_200`: `close > SMA200` 그리고 `SMA200 slope > 0`
- `above_200_weak`: `close > SMA200` 이지만 `SMA200 slope <= 0`
- `below_200_recovery`: `close < SMA200`이지만 회복 시도(EMA/구조)가 있는 구간
- `below_200_downtrend`: `close < SMA200` + 하락 구조 지속 구간

### 전략 정책 적용(현재 기본)
- 현재 기본 정책은 보수적으로 `bull_above_200` 중심 실행을 우선합니다.
- 나머지 레짐은 reject reason으로 분리 기록되어, “전략 실패 vs 레짐 부적합”을 해석할 수 있습니다.
- 구조상 향후 `above_200_weak`/`below_200_recovery` 전용 정책으로 확장 가능합니다.

### 왜 BTC/ETH 레짐 분석을 먼저 봐야 하나
- 전략 실행 전 구간이 어떤 레짐 비중인지 확인하면, 결과 해석 왜곡을 줄일 수 있습니다.
- 예: 거래가 거의 없을 때 전략이 나쁜 게 아니라 `below_200_downtrend` 비중이 높았을 수 있습니다.

### 레짐 분석 API
- `GET /regime/analyze`
  - 입력: `symbol`, `indicator_start`, `analysis_start`, `analysis_end`
  - 출력: daily 지표, 레짐 카운트, above/below 200 세그먼트, 세그먼트 수익률
- `GET /regime/analyze/batch`
  - 입력: `symbols`, `indicator_start`, `analysis_start`, `analysis_end`
  - 출력: 심볼별 레짐 분석 + 배치 요약

## 추가 전략: trend_momentum_volume_score_v2

### 목적
- 횡보장 오진입, 과확장 추격, 약한 모멘텀 신호, 저품질 캔들 진입을 줄이는 단기 추세형 전략

### 핵심 로직
- 1h(또는 trend role) 추세 정렬:
  - `EMA20 > EMA50`, `EMA20 slope > 0`, `close > EMA20`
- 5m(또는 entry role) pullback reclaim:
  - 최근 4~5봉 내 EMA20 눌림(low <= EMA20) + 현재 close > EMA20
- 모멘텀:
  - RSI 또는 MACD 중 하나 이상 긍정
- 추가 필터:
  - 거래량 급증
  - 캔들 품질(양봉 + body/range)
  - ATR 기반 과확장 방지
  - ATR% 변동성 체제 범위

### 잘 맞는 시장
- 방향성이 명확하고 pullback 후 재가속이 자주 나오는 추세장
- 거래량이 추세 방향으로 동반되는 구간

### 약한 시장
- 장시간 횡보/노이즈 장
- 급격한 변동성 붕괴 또는 이벤트성 스파이크 구간
- 유동성 저하로 캔들 품질/체결 품질이 떨어지는 구간

## 추가 전략: mtf_trend_pullback_v2

### v1 대비 핵심 차이
- 진입 확인 강화:
  - `trend(1d)`: `close > EMA50`, `EMA20 > EMA50`, `EMA50 slope >= 0`
  - `setup(60m)`: EMA50 위 눌림 + RSI 범위(기본 40~60) + lower-low 붕괴 회피
  - `entry(15m)`: EMA20 reclaim 또는 local high break + 거래량 확인
- 추격 매수 방지:
  - `max_distance_from_60m_ema20_pct`
  - `max_atr_extension`
- 손절 개선:
  - `ATR + swing low` 기반 stop
  - `min_stop_pct`, `max_stop_pct`로 과도/과소 리스크 차단
- 청산 개선:
  - `regime_reversal_confirm_bars` 확인 청산
  - `daily_trend_bearish`, `time_stop` 조건 추가
- 재진입 억제:
  - `cooldown_after_stop`(손절 후 12h, 연속 2회 손절 후 48h 기본)

### 역할 매핑
- `required_roles`: `trend`, `setup`, `entry`
- `default_timeframe_mapping`:
```json
{
  "trend": "1d",
  "setup": "60m",
  "entry": "15m"
}
```

### 주요 reject_reason
- `trend_not_bullish`, `1d_trend_bearish`
- `setup_not_pullback`, `rsi_out_of_range`
- `no_reclaim_trigger`, `volume_not_confirmed`
- `chase_filter_blocked`
- `stop_too_tight`, `risk_too_wide`
- `cooldown_after_stop`

### sweep 후보 파라미터 예시
```json
{
  "setup_rsi_min": [38, 40, 42],
  "setup_rsi_max": [58, 60, 62],
  "entry_volume_multiplier": [1.0, 1.1, 1.2],
  "max_distance_from_60m_ema20_pct": [2.0, 2.5, 3.0],
  "max_atr_extension": [1.3, 1.5, 1.8],
  "atr_stop_mult": [1.6, 1.8, 2.0],
  "min_stop_pct": [0.6, 0.8, 1.0],
  "max_stop_pct": [3.0, 3.5, 4.0],
  "regime_reversal_confirm_bars": [2, 3],
  "after_stop_loss_hours": [12, 24]
}
```

## 추가 전략: mtf_confluence_pullback_v2 (Spot Long-Only MTF Confluence)

### 왜 추가했나
- 15분봉 단독 판단을 피하고, 큰 흐름→중간 구조→짧은 확인→체결 최적화 순서로 진입 품질을 높이기 위해 추가한 전략입니다.
- 핵심은 `1d/MA200`을 최상위 필수 게이트로 두고, `4h/1h/30m/15m/5m` 역할을 분리하는 것입니다.

### 역할 매핑
- `required_roles`: `regime`, `trend`, `setup`, `trigger`
- `optional_roles`: `confirmation`, `execution`
- `default_timeframe_mapping`:
```json
{
  "regime": "1d",
  "trend": "4h",
  "setup": "1h",
  "confirmation": "30m",
  "trigger": "15m",
  "execution": "5m"
}
```

### Bull 전용 완화 variant: `bull_above_200_long_v1_looser`
- 목적: baseline `mtf_confluence_pullback_v2`의 철학(상승장 하드 게이트)은 유지하면서, bull 구간에서 과도한 진입 누락을 줄이기 위한 완화 버전입니다.
- 이 variant는 recovery 전략이 아니라 **상승장 메인 전략의 완화형**입니다.

핵심 완화 포인트:
1. `higher_timeframe_trend_weak` 완화:
   - `allow_trend_alt_gate=true`
   - `trend_structure_tolerance_pct` 확대
2. setup 완화:
   - `setup_rsi_min/max`: `40~60` -> `35~68`
   - `setup_pullback_near_pct` 확대
   - `setup_lower_low_tolerance_pct` 도입
3. trigger 완화:
   - `require_local_high_break=false`
   - `allow_reclaim_bullish_without_high_break=true`
   - `entry_volume_multiplier` 완화 (`1.1` -> `1.05`)
4. regime 하드 게이트 유지:
   - `1d close > SMA200`, `SMA200 slope > 0`, EMA stack 조건 체계 유지

요약:
- `mtf_confluence_pullback_v2`: 보수적 baseline (신호 품질 최우선)
- `bull_above_200_long_v1_looser`: bull continuation에서 진입 기회 확장
- `below_200_recovery_long_v1*`: below-200 recovery 전용 (역할 분리 유지)

## 추가 전략: below_200_recovery_long_v1 (Below-200 Recovery Long-Only)

### 왜 필요한가
- `mtf_confluence_pullback_v2`는 `bull_above_200` 메인 구간 판단에 강점을 둔 전략입니다.
- 다만 `below_200_recovery` 회복 초입 구간에서는 진입이 매우 보수적일 수 있어, 회복장 전용 전략을 별도로 분리했습니다.

### 역할 분리
- `mtf_confluence_pullback_v2`: `bull_above_200` 메인 전략
- `below_200_recovery_long_v1`: `below_200_recovery` 전용 전략
- `below_200_downtrend`: no-trade 정책 유지

### 전략 요약
- mode: `multi_timeframe`
- spot 제약: `spot_long_only=true` (long-or-flat)
- required roles: `regime`, `trend`, `setup`, `trigger`
- optional roles: `execution`
- default mapping:
```json
{
  "regime": "1d",
  "trend": "4h",
  "setup": "1h",
  "trigger": "15m",
  "execution": "5m"
}
```

### 핵심 게이트
1. regime가 `below_200_recovery`일 것
2. `below_200_downtrend`에서는 진입 금지
3. 4H higher-low/회복 구조 + 15M reclaim trigger 확인
4. 리스크 필터(stop distance) 통과

### 리스크/청산
- 손절: `ATR + swing low` 기반 (`atr_stop_mult=1.6` 기본)
- 회복장 전략 특성상 `time_stop_hours=48` 기본으로 상대적으로 빠른 정리 허용
- 손절 후 cooldown:
  - 1회 손절 후 12h
  - 2연속 손절 후 36h

### 주요 reject_reason 예시
- `not_below_200_recovery`
- `too_far_below_sma200`
- `daily_recovery_not_confirmed`
- `trend_higher_low_missing`
- `setup_not_pullback`
- `no_trigger_reclaim`
- `execution_overextended`
- `risk_too_wide`
- `stop_too_tight`
- `cooldown_after_stop`

### sweep 파라미터 예시
```json
{
  "max_distance_below_sma200_pct": [8.0, 12.0],
  "setup_rsi_min": [40.0, 42.0],
  "setup_rsi_max": [60.0, 62.0],
  "trigger_volume_multiplier": [1.0, 1.1, 1.2],
  "atr_stop_mult": [1.4, 1.6, 1.8],
  "min_stop_pct": [0.7, 0.9],
  "max_stop_pct": [2.5, 3.0],
  "time_stop_hours": [36, 48],
  "entry_score_threshold": [65, 70],
  "after_stop_loss_hours": [12, 24]
}
```

### 단계적 완화 variant (base: `below_200_recovery_long_v1_looser_regime`)
- `below_200_recovery_long_v1_looser_setup`
  - 목적: regime 통과 후 setup 병목 완화
  - 핵심 변경:
    - `setup_rsi_min/max`: `42~62` -> `38~68`
    - `setup_pullback_near_pct`: `1.2` -> `2.0`
    - `reject_lower_low`: `true` -> `false` (미세 lower-low 허용)
  - 줄이고 싶은 거절 사유:
    - `setup_not_pullback`
    - `setup_rsi_out_of_range`
    - `setup_lower_low_break`

- `below_200_recovery_long_v1_looser_trigger`
  - 목적: setup 통과 후 trigger 병목 완화
  - 핵심 변경:
    - `require_local_high_break`: `true` -> `false`
    - `trigger_volume_multiplier`: `1.1` -> `1.0`
    - `entry_score_threshold`: 소폭 완화
  - 줄이고 싶은 거절 사유:
    - `no_local_high_break`
    - `trigger_volume_not_confirmed`
    - `no_trigger_reclaim` (간접 완화)

### 이번 실험 해석 포인트
1. ETH에서 `trade_count`가 0을 벗어나는지
2. BTC에서 과매매(`trade_count` 급증)가 발생하지 않는지
3. 거절 사유가 regime 중심에서 setup/trigger 중심으로 이동하는지
4. 통과한 variant를 다음 단계 walk-forward 후보로 채택할지 판단

### 향후 확장
- `below_200_recovery_long_v2` (recovery 구조 강화)
- recovery + breakeven stop 옵션
- `above_200_weak` 전용 보수 전략 추가

### 점수제 + 필수 게이트
- 가중치: regime 30, trend 25, setup 20, confirmation 10, trigger 10, execution 5
- 진입은 아래를 동시에 만족해야 합니다.
  1. `1d close > MA200`
  2. `MA200 slope > 0`
  3. 4h trend 미붕괴
  4. 15m trigger 성립
  5. stop distance가 허용 범위(`min_stop_pct ~ max_stop_pct`) 내
  6. 총점 `entry_score_threshold` 이상

### 핵심 필터/리스크
- chase filter:
  - `max_distance_from_setup_ema_pct`
  - `max_trigger_atr_extension`
- stop:
  - `min(swing_low - swing_buffer_atr*ATR, entry - atr_stop_mult*ATR)` (trigger TF 기준)
- cooldown:
  - 손절 후 12h, 연속 손절 2회면 48h(기본)
- 주요 거절 사유:
  - `regime_not_bullish`, `higher_timeframe_trend_weak`, `setup_not_pullback`
  - `chase_filter_blocked`, `execution_overextended`
  - `stop_too_tight`, `risk_too_wide`, `cooldown_after_stop`

### 현물 롱 전용
- `spot_long_only=true`
- 숏 진입 로직 없이 `long-or-flat` 상태만 허용합니다.

### sweep 예시
```json
{
  "max_distance_from_setup_ema_pct": [2.0, 2.5, 3.0],
  "max_trigger_atr_extension": [1.3, 1.5, 1.8],
  "atr_stop_mult": [1.6, 1.8, 2.0],
  "min_stop_pct": [0.6, 0.8, 1.0],
  "max_stop_pct": [3.0, 3.5, 4.0],
  "entry_volume_multiplier": [1.0, 1.1, 1.2],
  "setup_rsi_min": [38, 40, 42],
  "setup_rsi_max": [58, 60, 62],
  "after_stop_loss_hours": [12, 24]
}
```

## 추가 전략: turtle_breakout_v1 (Long Only)

### 전략 철학
- 예측보다 추세 추종
- 빠른 손절, 긴 추세 보유
- 승률보다 손익비/기대값 중심

### 핵심 규칙
- 진입(롱):
  - `breakout_entry_length` 기간(기본 20봉) 최고가를 종가 기준 상향 돌파
  - `require_trend_filter=true`면 `close > MA(trend_ma_length)` (기본 200)
- 손절:
  - `ATR(atr_length) * atr_stop_multiple` (기본 `ATR20 * 2.0`)
  - `stop_loss = entry_price - ATR * multiple`
- 청산:
  - `breakout_exit_length` 기간(기본 10봉) 최저 채널 하향 이탈 시 추세 종료로 판단
  - 현재 엔진에서는 해당 조건을 `regime='bearish'`로 내려 포지션 청산 경로를 재사용

### 주요 파라미터
- `breakout_entry_length` (20)
- `breakout_exit_length` (10)
- `trend_ma_length` (200)
- `atr_length` (20)
- `atr_stop_multiple` (2.0)
- `risk_per_trade_pct` (0.02)
- `require_trend_filter` (true)
- `use_close_breakout_only` (true)
- `allow_reentry_after_stop` (true, 현재는 메타데이터 성격)
- `min_atr_pct` / `max_atr_pct` (optional)

### 리스크 메타데이터
- 현재 단계는 정교한 포지션 사이징 엔진 없이, 아래를 `debug_info`로 기록:
  - ATR 값, stop distance, stop distance %
  - `risk_per_trade_pct`
  - 이론적 포지션 노셔널 배수(`theoretical_position_notional_multiple`)

### Sweep 예시
```json
{
  "breakout_entry_length": [20, 30, 55],
  "breakout_exit_length": [10, 15, 20],
  "atr_stop_multiple": [1.5, 2.0, 2.5],
  "trend_ma_length": [100, 200]
}
```

## 추가 전략: turtle_spot_long_v2 (Spot Long-Only MTF)

### 왜 일봉 MA200 필터가 중요한가
- 현물 시장은 숏 없이 롱/현금(Flat)만 운용하므로, 하락/약세 구간에서 억지 진입을 줄이는 게 핵심입니다.
- `turtle_spot_long_v2`는 진입 전 필수 게이트로 아래 2개를 모두 요구합니다.
  - `daily close > daily MA200`
  - `daily MA200 slope > 0`
- 여기서 MA200은 **반드시 일봉(1d) 기준 200일 이동평균**입니다.

### 전략 요약
- 모드: `multi_timeframe`
- 현물 제약: `spot_long_only=true` (short 미사용, long-or-flat)
- 기본 매핑:
  - `trend=1d` (필수)
  - `setup=240m` (선택)
  - `entry=60m` (필수)

### 진입/손절/청산
- 진입:
  1. 일봉 MA200 상승 추세 필수 게이트 통과
  2. entry timeframe에서 `N`봉 종가 돌파(기본 20)
  3. 선택적으로 setup/거래량/과확장/변동성 필터
- 손절:
  - `ATR(entry_tf, 20) * atr_stop_multiple(기본 2.0)`
- 청산:
  - `breakout_exit_length` 채널 하향 이탈(기본 10)
  - ATR stop
  - 테스트 종료

### 핵심 파라미터(스윕 예시)
```json
{
  "breakout_entry_length": [20, 30, 55],
  "breakout_exit_length": [10, 11, 20],
  "atr_stop_multiple": [1.5, 2.0, 2.5],
  "trend_slope_lookback": [10, 20, 30]
}
```

### 왜 long-or-flat인가
- 약세장에서 현물 계좌는 숏으로 방어할 수 없으므로, 무리한 진입보다 관망이 손익비에 유리합니다.
- 본 전략은 하락장에서는 진입을 차단하고 추세장만 선별해 기대값을 확보하는 구조입니다.

### 향후 확장 아이디어
- setup role 강화(구조/추세 판단)
- volume confirmation 강화
- `trend=1d + entry=15m` 조합 세분화
- paper trading에 동일 전략 인터페이스 적용

## 파라미터 스윕 (Grid Sweep Skeleton)

### 개념
- `sweep_space`를 입력하면 Cartesian product 방식으로 조합을 생성합니다.
- 각 조합은 기존 `BacktestService.run`을 재사용해 실행합니다.
- 결과는 `sweep_run`으로 저장되고 조합별 성과와 상위 랭킹을 함께 제공합니다.
- 이번 단계는 deterministic grid sweep만 지원합니다. (Optuna/Bayesian/random search 미포함)

### sweep_space 예시
```json
{
  "score_threshold": [0.6, 0.7, 0.8],
  "volume_multiplier": [1.0, 1.2]
}
```

### 결과 해석 포인트
- `best_by_net_return`: 순수익률 기준 최고 조합
- `best_by_excess_return`: 벤치마크 초과수익 기준 최고 조합
- `lowest_drawdown_group`: 낙폭이 낮은 상위 그룹
- `top_n`: 기본 net return 내림차순 상위 조합
- `profitable_count` / `losing_count`: 수익/손실 조합 개수

## 업비트 과거 데이터 수집/검증

### 수집 흐름
1. `collect` 요청으로 업비트 과거 캔들 수집
2. symbol/timeframe 디렉터리 규칙으로 저장
3. dedupe + data_signature 계산
4. 품질 검사(정렬/중복/결측/간격/OHLC/기초 이상치)
5. manifest + quality report 저장

### 멀티 타임프레임/배치 흐름
1. `collect-batch` 또는 `update-batch` 요청에서 `symbols x timeframes` 조합 생성
2. 각 조합을 독립 dataset으로 수집/갱신
3. `validate_after_collect=true`면 조합별 품질 검사 자동 실행
4. 부분 실패를 허용하고, 조합별 성공/실패/스킵 결과를 집계
5. `summary`에서 symbol/timeframe 단위 품질 상태를 한 번에 조회

### Top10 Universe 자동 선정/수집
- 목적:
  - 업비트 거래 가능 마켓 중에서 시가총액 상위 유니버스를 자동 선정하고, 해당 유니버스 전체 데이터를 일괄 수집/갱신
- 선정 기준:
  1. Upbit `market/all`에서 거래 가능 마켓 조회
  2. 외부 시가총액 소스(CoinGecko markets) 조회
  3. `KRW-*`(기본) 마켓과 교차
  4. 시가총액 내림차순 Top 10 선정
- 유니버스 저장:
  - `data/universes/upbit_top10_marketcap/current.json`
  - `data/universes/upbit_top10_marketcap/snapshots/*.json`
- 포함 타임프레임(기본):
  - `1m, 3m, 5m, 10m, 15m, 30m, 60m, 240m, 1d, 1w, 1mo, 1y`
- 초봉 옵션:
  - `include_seconds=true`일 때 `1s` 포함
  - Upbit 초봉 제약(최근 구간 중심)을 고려해 보수적으로 사용 권장

### 저장 규칙
- 경로: `data/market/upbit/{symbol}/{timeframe}/`
- 파일:
  - `candles.csv`
  - `manifest.json`
- manifest 주요 필드:
  - `dataset_id`, `source`, `symbol`, `timeframe`
  - `start_at`, `end_at`, `row_count`
  - `data_signature`, `quality_status`
  - `collector_version`, `code_version`, `last_checked_at`

### 품질 검사 항목
- timestamp 정렬
- duplicate timestamp 개수
- null/empty 값 개수
- timeframe 간격 기준 missing interval 개수
- OHLC 무결성(high/low 범위, 음수 가격/거래량)
- suspicious gap(큰 간격) 개수

### 품질 상태 해석
- `pass`: 치명 이슈 없음
- `warning`: 중복/간격 이상/의심 gap 존재
- `fail`: 정렬 실패, null 다수, invalid OHLC 등 치명 이슈

### 백테스트/워크포워드 연결
- 동일 symbol/timeframe의 collected 데이터가 있고 quality가 `fail`이 아니면, provider가 sample보다 우선 사용합니다.
- 따라서 수집/검증된 데이터셋이 즉시 backtest/walk-forward 입력으로 연결됩니다.

## API

### 주요 백테스트 API
- `POST /backtests/run`
- `GET /backtests/{run_id}`
- `POST /backtests/rerun/{run_id}`
- `GET /backtests/compare?run_ids=...`
- `GET /backtests/recent`

백테스트 요청에서 warmup 관련 확장:
- `indicator_start`(optional)
- `warmup_days`(optional)

### Walk-Forward API
- `POST /walkforward/run`
- `GET /walkforward`
- `GET /walkforward/{walkforward_run_id}`
- `POST /walkforward/rerun/{walkforward_run_id}`
- `GET /walkforward/compare?walkforward_run_ids=...`
- `GET /walkforward/compare.csv?walkforward_run_ids=...` (비교 결과 CSV)
- `POST /walkforward/batch-run` (여러 symbol/mode 일괄 실행 골격)
- `POST /walkforward/jobs`
- `GET /walkforward/jobs`
- `GET /walkforward/jobs/{job_id}`
- `POST /walkforward/jobs/{job_id}/cancel`
- `POST /walkforward/jobs/{job_id}/retry`

워크포워드 요청에서도 동일하게:
- `indicator_start`(optional)
- `warmup_days`(optional)

### Sweep API
- `POST /sweeps/run`
- `GET /sweeps`
- `GET /sweeps/{sweep_run_id}`
- `POST /sweeps/rerun/{sweep_run_id}`
- `GET /sweeps/{sweep_run_id}/results`
- `GET /sweeps/{sweep_run_id}/top`
- `GET /sweeps/jobs`
- `GET /sweeps/jobs/{job_id}`
- `POST /sweeps/jobs/{job_id}/cancel`
- `POST /sweeps/jobs/{job_id}/retry`

#### 멀티 타임프레임 실행 예시 (Backtest)
```bash
curl -X POST http://localhost:8000/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "mtf_trend_pullback_v1",
    "symbol": "BTC-KRW",
    "timeframe": "5m",
    "timeframe_mapping": {
      "trend": "60m",
      "setup": "15m",
      "entry": "5m"
    },
    "start_date": "2025-01-01",
    "end_date": "2025-12-31"
  }'
```

### Market Data API
- `POST /market-data/collect`
- `POST /market-data/update`
- `POST /market-data/collect-batch`
- `POST /market-data/update-batch`
- `GET /market-data`
- `GET /market-data/summary`
- `GET /market-data/by-symbol/{symbol}`
- `GET /market-data/{dataset_id}`
- `POST /market-data/{dataset_id}/validate`
- `GET /market-data/{dataset_id}/preview`
- `GET /market-data/jobs`
- `GET /market-data/jobs/{job_id}`
- `POST /market-data/jobs/{job_id}/cancel`
- `POST /market-data/jobs/{job_id}/retry`
- `POST /market-data/top10-universe/refresh`
- `GET /market-data/top10-universe`
- `POST /market-data/top10-universe/collect-all`
- `POST /market-data/top10-universe/update-all`
- `GET /market-data/top10-universe/summary`
- `GET /market-data/top10-universe/missing`
- `POST /market-data/top10-universe/retry-missing`

### 작업 큐 API
- `POST /backtests/jobs`
- `GET /backtests/jobs`
- `GET /backtests/jobs/{job_id}`
- `POST /backtests/jobs/{job_id}/cancel`
- `POST /backtests/jobs/{job_id}/retry`

### Regime 분석 API
- `GET /regime/analyze`
- `GET /regime/analyze/batch`

### 전략/기타 API
- `GET /health`
- `GET /strategies`
- `GET /strategies/{strategy_id}`
- `GET /strategies/{strategy_id}/params`
- `PUT /strategies/{strategy_id}/params`
- `GET /symbols`
- `GET /signals/{symbol}`

### Chart API
- `GET /charts/candles`
- `GET /charts/indicators`
- `GET /charts/backtest-overlay`

차트 지표:
- `EMA20`, `EMA50`, `EMA120`, `RSI14`, `volume_ma20`

차트 데이터 선택 정책:
- collected + validated dataset 우선
- 없으면 sample fallback
- 응답 `dataset` 메타데이터로 source/dataset_id/quality 확인

프론트 차트 구현:
- `Apache ECharts` 사용 (멀티 패널 캔들/거래량/RSI + 오버레이 확장이 쉬워 유지보수에 유리)

## 프론트 화면
- `/backtests`
  - fee/slippage/execution_policy/benchmark 입력
  - 비동기 작업 진행률/취소/재시도
  - 최근 run 비교
- `/backtests/[run_id]`
  - gross/net/비용/benchmark 카드
  - equity curve + benchmark curve
  - 차트 섹션(캔들/EMA/RSI/거래 오버레이)
  - params_snapshot / execution_config 표시
  - 거래별 비용 컬럼 표시
- `/walkforward`
  - train/test/step/window/execution 설정 입력
  - 비동기 walk-forward job 진행률 표시
  - 최근 실행 목록 및 rerun
- `/walkforward/compare`
  - 여러 walk-forward 실행 선택 비교
  - 총 수익/평균 segment/benchmark 초과 구간 수 비교
  - 선택 결과 CSV 내보내기
- `/walkforward/[walkforward_run_id]`
  - 세그먼트 요약 카드
  - 세그먼트별 수익률 시각화(bar)
  - 세그먼트 표 + linked backtest run 상세 이동
- `/market-data`
  - 멀티 심볼/멀티 타임프레임 batch collect/update 실행
  - Top10 유니버스 새로 계산/전체 수집/전체 갱신
  - 누락 조합 조회 및 누락 조합만 재시도
  - include_seconds / overwrite_existing / validate_after_collect 제어
  - symbols x timeframes 조합 수, 배치 결과(성공/실패/스킵) 확인
  - summary 카드(pass/warning/fail, symbols, timeframes) 확인
  - batch job 진행률 및 현재 처리 조합 확인
- `/market-data/[dataset_id]`
  - manifest 상세
  - quality report 카드
  - preview 데이터 확인
  - validate 재실행
- `/charts`
  - symbol/timeframe/date range 기반 정적 분석 차트
  - indicator toggle(EMA20/50/120, RSI14, volume)
  - run_id 오버레이(매수/매도 마커, exit reason, gross/net)
  - MTF run의 timeframe_mapping 표시
- `/sweeps`
  - sweep 실행 폼(strategy/symbol/timeframe(_mapping)/기간/sweep_space)
  - sweep 목록(조합 수/평균 수익/상위 수익)
  - sweep job 진행률 확인
- `/sweeps/[sweep_run_id]`
  - top 조합 테이블
  - 전체 조합 결과(status/error 포함)
  - related backtest run 링크

## 로컬 실행

### 1) Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

확인:
- [http://localhost:8000/health](http://localhost:8000/health)
- [http://localhost:8000/docs](http://localhost:8000/docs)

### 2) Frontend
```bash
cd frontend
npm install
npm run dev
```

접속:
- [http://localhost:3000](http://localhost:3000)

API 주소 변경이 필요하면:
```bash
# frontend/.env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 샘플 백테스트 실행
```bash
curl -X POST http://localhost:8000/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "ma_regime_v1",
    "symbol": "BTC-KRW",
    "timeframe": "1d",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "fee_rate": 0.0005,
    "slippage_rate": 0.0003,
    "execution_policy": "next_open",
    "benchmark_enabled": true
  }'
```

## 리포트 읽는 방법 (핵심)
- `gross_return_pct`는 비용 미반영 성과
- `net_return_pct`는 수수료+슬리피지 반영 성과
- `cost_drag_pct`가 클수록 “거래비용에 약한 전략”
- `strategy_excess_return_pct`가 음수면 같은 기간 단순 보유보다 열위

## 테스트
```bash
cd backend
source .venv/bin/activate
pytest -q
```

현재 포함:
- 전략 유닛 테스트
- 백테스트 엔진(수수료/슬리피지/체결정책/벤치마크) 테스트
- rerun 재현성 테스트(실행 설정 포함)
- compare 응답 구조 테스트(비용/벤치마크 필드 포함)
- charts API 테스트(candles/indicators/overlay/MTF mapping)
- turtle_breakout_v1 규칙 테스트(돌파/추세필터/ATR손절/exit channel)
- mtf_trend_pullback_v2 규칙 테스트(추세/셋업/트리거/chase/stop/cooldown)
- turtle_breakout_v1 백테스트/워크포워드/스윕 연동 테스트
- mtf_trend_pullback_v2 백테스트/워크포워드/스윕 연동 테스트
- job API / repository 테스트
- walk-forward 세그먼트 분할 테스트
- walk-forward 실행/저장/rerun/API/job progress 테스트

## 데이터 파일
- `data/sample/BTC-KRW_1d.csv`
- `data/sample/ETH-KRW_1d.csv`
- `data/sample/SOL-KRW_1d.csv`
- `data/sample/XRP-KRW_1d.csv`
- `data/market/upbit/{symbol}/{timeframe}/candles.csv`
- `data/market/upbit/{symbol}/{timeframe}/manifest.json`

형식:
- `timestamp,open,high,low,close,volume`

## 다음 단계 추천
1. walk-forward train 구간 튜닝(in-sample best params 적용)
2. anchored/rolling 구간별 best params 선택 정책
3. sweep 정렬 기준 확장(net/excess/MDD 복합 점수)
4. multi-timeframe 전략 템플릿 확대
5. paper trading 준비(실행 어댑터 확장)
6. turtle 확장: 숏 버전, trend timeframe 분리, 피라미딩

## v2 비교 실험 가이드

### 비교 대상
- A. `mtf_trend_pullback_v1`
- B. `mtf_trend_pullback_v2` 기본형
- C. `v2 + 1R breakeven` (옵션 플래그)
- D. `v2 + 2R trailing` (옵션 플래그)
- E. `v2 + cooldown 강화`

### 권장 기간
- 최근 3개월
- 이전 3개월
- 전체 6개월

### 추천 지표
- `net_return_pct`, `benchmark_buy_and_hold_return_pct`, `strategy_excess_return_pct`
- `trade_count`, `win_rate`, `max_drawdown`
- `avg_profit`, `avg_loss`, `cost_drag_pct`
- `exit_reason_counts`, `reject_reason_counts`
- `profit_factor`, `expectancy_per_trade`, `max_consecutive_losses`

## 백테스트 리포트 해석 가이드(확장 지표)

- `buy_and_hold_return_pct`: 같은 기간 단순 보유 수익률
- `excess_return_vs_buy_and_hold`: 전략 순수익률(`net`) - 단순 보유 수익률. 양수면 벤치마크 초과
- `profit_factor`: `총 이익 거래 수익 합 / 총 손실 거래 절대값 합`
- `expectancy_per_trade`: 거래 1건당 기대 수익률 평균(`net_pnl_pct` 평균)
- `max_consecutive_losses`: 연속 손실 거래의 최대 길이
- `avg_holding_time`: 평균 보유 시간(시간 단위)
- `exposure_pct`: 백테스트 기간 중 실제 포지션 보유 시간 비율
- `cost_drag_pct`: `gross_return_pct - net_return_pct` (비용이 성과에서 깎아낸 비율)
- `R_multiple`: `(해당 거래 순손익 금액) / (진입 시 손절 거리 금액)`

상세 리포트에서 반드시 함께 볼 것:
- 핵심 카드: `net`, `buy_and_hold`, `excess`, `profit_factor`, `max_drawdown`, `max_consecutive_losses`
- 로그 품질: `entry_reason`, `exit_reason`, `holding_time`, `R_multiple`, `MFE/MAE`
- 구조적 진단: `reject_reason_counts`, `exit_reason_counts`
- 일관성 진단: `monthly_returns`(월별 성과가 특정 구간에만 편중되는지 확인)

### 합격 기준(초안)
- 최근 3개월: `net_return > v1`, `MDD <= v1`, `trade_count >= 10`
- 더 엄격한 기준:
  - 최근/이전 3개월 모두 생존
  - 6개월 구간 `MDD <= 15%`, `net return > 0`
  - `max_consecutive_losses <= 4`, 벤치마크 초과수익 양수
### Batch 실행 골격
- `walkforward/batch-run`은 여러 symbol/mode 조합 요청을 한 번에 생성합니다.
- `use_jobs=true`면 각 조합이 walk-forward job으로 등록됩니다.
- 현재 단계에서는 고급 스케줄링/분산 없이 로컬 큐 기반으로 동작합니다.
