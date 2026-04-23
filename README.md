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

### 미래 데이터 누수 방지 원칙
- entry role의 현재 시점(`as_of`)을 기준으로 각 role(trend/setup/entry)은 `as_of` 이하로 확정된 봉만 사용합니다.
- 즉, 상위/중간 timeframe에서 아직 확정되지 않은 미래 봉은 참조하지 않습니다.
- 구현상 전략 컨텍스트 생성 시 role별 히스토리를 `timestamp <= as_of`로 잘라 전달합니다.

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

### 작업 큐 API
- `POST /backtests/jobs`
- `GET /backtests/jobs`
- `GET /backtests/jobs/{job_id}`
- `POST /backtests/jobs/{job_id}/cancel`
- `POST /backtests/jobs/{job_id}/retry`

### 전략/기타 API
- `GET /health`
- `GET /strategies`
- `GET /strategies/{strategy_id}`
- `GET /strategies/{strategy_id}/params`
- `PUT /strategies/{strategy_id}/params`
- `GET /symbols`
- `GET /signals/{symbol}`

## 프론트 화면
- `/backtests`
  - fee/slippage/execution_policy/benchmark 입력
  - 비동기 작업 진행률/취소/재시도
  - 최근 run 비교
- `/backtests/[run_id]`
  - gross/net/비용/benchmark 카드
  - equity curve + benchmark curve
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
  - symbols x timeframes 조합 수, 배치 결과(성공/실패/스킵) 확인
  - summary 카드(pass/warning/fail, symbols, timeframes) 확인
  - batch job 진행률 및 현재 처리 조합 확인
- `/market-data/[dataset_id]`
  - manifest 상세
  - quality report 카드
  - preview 데이터 확인
  - validate 재실행
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
### Batch 실행 골격
- `walkforward/batch-run`은 여러 symbol/mode 조합 요청을 한 번에 생성합니다.
- `use_jobs=true`면 각 조합이 walk-forward job으로 등록됩니다.
- 현재 단계에서는 고급 스케줄링/분산 없이 로컬 큐 기반으로 동작합니다.
