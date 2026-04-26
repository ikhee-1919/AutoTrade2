# Architecture Notes (Backtest + Walk-Forward + Market Data)

## 목표
- 전략은 코드에서만 관리하고, 웹은 운영/검증 콘솔 역할에 집중
- 백테스트 결과에 현실적인 비용/체결 가정을 반영
- rerun/compare에서 재현 가능한 실행 메타데이터 유지
- walk-forward 세그먼트 분석(저장/조회/rerun/job) 골격 제공
- 업비트 과거 데이터 수집/검증/저장 관리 계층 제공

## 레이어 분리
- `frontend/`: 실행 폼, 결과 리포트, 비교, 작업 이력
- `backend/app/api`: HTTP 라우터 + 응답 스키마
- `backend/app/services`: 유스케이스 orchestration
- `backend/app/backtest`: 시뮬레이션 엔진
- `backend/app/services/walkforward_service.py`: 세그먼트 orchestration
- `backend/app/services/walkforward_job_service.py`: walk-forward 비동기 실행
- `backend/app/services/market_data_service.py`: collect/update/collect-batch/update-batch/summary orchestration
- `backend/app/services/market_data_job_service.py`: market-data 단건/배치 비동기 실행
- `backend/app/services/parameter_sweep_service.py`: grid sweep orchestration
- `backend/app/services/parameter_sweep_job_service.py`: sweep 비동기 실행
- `backend/app/services/chart_service.py`: candles/indicators/overlay 조회 및 계산
- `backend/app/services/regime_classifier.py`: 200일선 기반 시장 상태 분류기
- `backend/app/services/regime_analysis_service.py`: 레짐 구간 분석(above/below 200 segment)
- `backend/app/strategy`: 전략 인터페이스 + 샘플 전략
- `backend/app/data/providers`: CSV 공급자(향후 Upbit 공급자 교체)
- `backend/app/data_collectors/upbit_collector.py`: 업비트 과거 캔들 수집기
- `backend/app/repositories`: run/job 저장소(JSON)
- `backend/app/execution`: future paper/live adapter 인터페이스

## 정적 분석 차트

### 차트 API
- `/charts/candles`: symbol/timeframe/date range 캔들 조회
- `/charts/indicators`: EMA20/50/120, RSI14, volume_ma20 계산
- `/charts/backtest-overlay`: run_id 기준 매수/매도 오버레이 조회

### 프론트 차트 레이어
- `/charts`: 분석 워크스페이스(캔들 + 거래량 + RSI + indicator toggle)
- `/backtests/[run_id]`: 상세 리포트 내부 차트 섹션에서 동일 컴포넌트 재사용
- 차트는 ECharts 멀티 패널 구성으로 구현하여 오버레이/MACD/regime 확장 포인트 확보

### 데이터 일관성
- 차트 조회도 provider의 collected 우선/fallback 정책을 동일하게 사용
- 응답에 dataset metadata를 포함해 source/sample/quality를 화면에서 확인
- run overlay는 run metadata(`strategy_version`, `code_version`, `timeframe_mapping`)를 함께 노출

## Warmup/Indicator Window 분리

### 문제 배경
- `insufficient_regime_history`는 전략 실패가 아니라, 레짐 계산용 일봉 히스토리 부족 상태를 의미합니다.
- 따라서 실행 구간과 지표 계산 구간을 분리해야 합니다.

### 현재 처리
- 요청은 `indicator_start` 또는 `warmup_days`를 받을 수 있습니다.
- 데이터 로드는 `indicator_start ~ trade_end`
- 성과 집계는 `trade_start ~ trade_end`
- run metadata에 아래를 함께 저장합니다.
  - `indicator_start`
  - `warmup_start`
  - `trade_start`
  - `trade_end`

## 200일선 레짐 분류기

### 분류 상태
- `bull_above_200`
- `above_200_weak`
- `below_200_recovery`
- `below_200_downtrend`
- (메타) `insufficient_history`

### 의도
- 200일선을 단순 on/off 게이트가 아니라 “시장 상태 분류기”로 사용
- 전략 거절 사유를 구조적으로 분해해 해석 가능성 확보

## Regime별 전략 역할 분리

- `mtf_confluence_pullback_v2`
  - 목적: `bull_above_200` 메인 구간의 MTF 컨플루언스 진입
  - 성격: 추세 지속형, 보수적 진입
- `below_200_recovery_long_v1`
  - 목적: `below_200_recovery` 전용 회복장 진입
  - 성격: 회복 확인 후 진입, 손절/시간청산 상대적으로 짧게 운영
- `below_200_downtrend`
  - 정책: no-trade

위 분리는 기존 메인 전략을 억지로 느슨하게 만들지 않고, 레짐별 전략을 독립적으로 검증/튜닝하기 위한 구조입니다.

## Regime 분석 API

- `GET /regime/analyze`
  - daily 지표, 레짐 카운트, above/below 200 연속 구간, 구간 수익률 반환
- `GET /regime/analyze/batch`
  - 다중 심볼(BTC/ETH 등) 동시 분석 및 요약 반환

이 API는 전략 실행 전 “해당 테스트 기간의 시장 상태”를 먼저 확인하는 용도로 설계되었습니다.

## 백테스트 현실화 핵심

### Execution Config
`execution_config`는 run metadata와 params_snapshot에 함께 저장:
- `execution_policy`: `next_open` | `signal_close`
- `fee_rate`, `entry_fee_rate`, `exit_fee_rate`
- `apply_fee_on_entry`, `apply_fee_on_exit`
- `slippage_rate`, `entry_slippage_rate`, `exit_slippage_rate`
- `benchmark_enabled`

### 엔진 산출물
- `summary`: gross/net, 비용, cost drag
- `trades`: intended/fill 가격, fee/slippage/cost, gross/net pnl
- `benchmark`: buy&hold return + excess return + benchmark curve
- `diagnostics`: reject reason / regime 분포
- `equity_curve`: 전략 자산곡선

## 멀티 타임프레임 전략 입력

### Timeframe Mapping
- 요청은 `timeframe`과 별도로 `timeframe_mapping`을 받을 수 있음
- 예: `{"trend":"60m","setup":"15m","entry":"5m"}`
- 단일 전략은 `entry` role 단일 매핑으로 하위 호환 유지

### Provider Bundle
- `CSVDataProvider.load_timeframe_bundle(...)`로 role별 캔들/메타를 한 번에 로드
- role별 선택 데이터셋(`source_type`, `dataset_id`, `dataset_signature`)을 run metadata에 저장

### Strategy Interface 확장
- single strategy: `evaluate(candles, params)`
- mtf strategy: `evaluate_context(context, params)`
- 공통 base 전략에서 `uses_context()`, `required_timeframe_roles()`, `default_timeframe_mapping()` 제공
- 전략 컨텍스트는 `runtime_state`를 선택적으로 포함해, MTF 전략이 cooldown/보유시간 기반 판단을 수행할 수 있음

### Future Leak 방지 원칙
- entry 시점 `as_of` 기준으로 role별 캔들은 `timestamp <= as_of`만 전략에 전달
- 상위/중간 timeframe의 미래 봉 참조를 금지하는 보수적 정렬 정책

## 재현성
- `strategy_version`
- `code_version` (git hash, fallback `unknown-local`)
- `params_hash`
- `data_signature`
- `params_snapshot`(전략 파라미터 + execution_config)

## Turtle Breakout v1 (Long-only)

### 규칙 요약
- 진입: 최근 `N`봉 최고 채널 종가 돌파(`breakout_entry_length`, 기본 20)
- 추세 필터: `close > MA(trend_ma_length)` (기본 200, optional)
- 손절: `ATR(atr_length) * atr_stop_multiple` (기본 ATR20*2.0)
- 청산: 최근 `M`봉 최저 채널 하향 이탈(`breakout_exit_length`, 기본 10)

### 엔진 연결 방식
- 백테스트 엔진의 기존 exit contract를 유지하기 위해, exit channel 하향 이탈 시 `regime='bearish'`를 반환해 청산 경로를 재사용
- 숏 진입은 구현하지 않고 long-only로 제한
- 리스크는 sizing 엔진 대신 `debug_info.risk_metadata`로 기록

## MTF Trend Pullback v2

### 목적
- `mtf_trend_pullback_v1`의 과도한 재진입/추격 진입을 줄이고 손실 구간 복구력을 높이기 위한 업그레이드 버전

### 핵심 변경
- 필수 3-role 매핑: `trend=1d`, `setup=60m`, `entry=15m`
- 추세 게이트: `1d close>EMA50`, `EMA20>EMA50`, `EMA50 slope >= 0`
- chase filter: `60m EMA20 거리` + `ATR extension` 동시 제한
- 손절: `ATR + swing low` 기반 stop + `min/max stop pct` 리스크 범위 제한
- 청산: 즉시 반전 청산 대신 `regime_reversal_confirm_bars` 확인 청산 + `daily_trend_bearish` + `time_stop`
- 손절 후 cooldown: stop-loss 연속 횟수에 따라 진입 제한 시간 확대

## Walk-Forward Skeleton

### 실행 모델
- 전체 요청 기간을 `train/test` 세그먼트로 분할
- 각 세그먼트의 test 구간 평가는 기존 `BacktestService.run` 재사용
- 엔진 중복 구현 없이 orchestration 계층에서 segment summary 집계
- 지원 모드:
  - `rolling`: train window 이동
  - `anchored`: train 시작 고정 + train 구간 확장

### 저장/조회
- `walkforward_run_repository`에 aggregate 저장
- segment별 `linked_run_id`로 기존 backtest 상세와 연결
- `request_hash`, `strategy_version`, `code_version`, `params_snapshot`, `execution_config` 저장
- compare 결과는 JSON API와 CSV export API를 함께 제공

## Parameter Sweep Skeleton

### 실행 모델
- 입력 `sweep_space`에서 Cartesian product로 조합 생성
- 각 조합은 기존 `BacktestService.run` 경로를 재사용
- 실패 조합이 있어도 나머지 조합을 계속 실행(부분 실패 허용)

### 저장/요약
- `sweep_run_id` 기준으로 run metadata + 조합별 결과 저장
- 조합 결과: `params_snapshot`, `related_run_id`, `net/gross`, `MDD`, `benchmark/excess`, `status`
- 요약/랭킹:
  - `best_by_net_return`
  - `best_by_excess_return`
  - `lowest_drawdown_group`
  - `top_n`
  - 수익/손실 조합 개수, 평균/중앙 수익률

### Job 연동
- `job_type=parameter_sweep`
- `progress = completed_combinations / total_combinations`
- request hash 기반 중복 실행 방지

## Market Data Management

### 저장 규칙
- collected root: `data/market`
- path: `data/market/upbit/{symbol}/{timeframe}/`
- artifacts:
  - `candles.csv`
  - `manifest.json`
- index:
  - `backend/app/data/market_data_datasets.json`

### 멀티 타임프레임 배치
- `symbols x timeframes` 카테시안 조합으로 batch collect/update 수행
- 각 조합은 독립 dataset + manifest + quality report를 유지
- 부분 실패를 허용하고 조합별 결과를 batch 응답/잡 메타데이터에 저장
- `summary`에서 symbol/timeframe별 품질 집계(pass/warning/fail) 조회

### 품질 검사
- 정렬/중복/null/missing interval/invalid OHLC/suspicious gap 검사
- `quality_status`: pass | warning | fail
- 결과는 manifest에 저장되고 API/UI에서 조회 가능

### 백테스트 연결
- `CSVDataProvider`가 collected dataset을 우선 탐색
- quality `fail`이 아닌 최신 dataset을 우선 사용
- 없으면 sample CSV fallback
- run metadata의 `data_signature`에 `dataset_id`/`dataset_signature`를 함께 남겨 재현성 연결

### Batch 실행 골격
- `POST /walkforward/batch-run`으로 symbol x mode 조합을 일괄 생성
- `use_jobs=true`일 때 조합별 walk-forward job을 큐에 등록
- 향후 scheduler/분산 처리로 확장 가능한 최소 인터페이스

### 현재 제약
- fixed-params walk-forward만 지원
- 고급 in-sample 최적화(파라미터 스윕) 미구현
- `window_unit=days`는 skeleton 단계에서 candle-step 기반 동작

### 확장 TODO
- in-sample tuning 인터페이스/결과 저장
- anchored/rolling 모드 분리
- multi-symbol walk-forward 배치 실행

## 향후 확장
1. 멀티 타임프레임 전략 입력 매핑(예: 1h trend + 5m entry)
2. 수집 스케줄러(batch update 자동화)
3. 슬리피지 모델 고도화(변동성/유동성 기반)
4. 파라미터 스윕 + walk-forward 고도화
5. anchored/rolling walk-forward 튜닝 전략 분리
6. paper trading adapter 구현 (실거래 전 단계)
