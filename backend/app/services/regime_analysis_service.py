from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from statistics import mean

from app.data.providers.csv_provider import CSVDataProvider
from app.services.regime_classifier import RegimeClassifier, RegimePoint


class RegimeAnalysisService:
    def __init__(self, data_provider: CSVDataProvider, classifier: RegimeClassifier | None = None) -> None:
        self._data_provider = data_provider
        self._classifier = classifier or RegimeClassifier()

    def analyze(
        self,
        symbol: str,
        indicator_start: date,
        analysis_start: date,
        analysis_end: date,
    ) -> dict:
        if indicator_start > analysis_start:
            raise ValueError("indicator_start must be <= analysis_start")
        if analysis_start > analysis_end:
            raise ValueError("analysis_start must be <= analysis_end")

        candles = self._data_provider.load_ohlcv(
            symbol=symbol,
            timeframe="1d",
            start_date=indicator_start,
            end_date=analysis_end,
        )
        points = self._classifier.classify_series(candles)
        filtered = [p for p in points if analysis_start <= date.fromisoformat(p.date) <= analysis_end]

        regime_counts = Counter(p.regime for p in filtered)
        above_points = [p for p in filtered if p.has_sufficient_history and p.above_sma200 is True]
        below_points = [p for p in filtered if p.has_sufficient_history and p.above_sma200 is False]

        regime_segments = self._build_segments(filtered, key_fn=lambda p: p.regime)
        above_segments = self._build_segments(
            [p for p in filtered if p.has_sufficient_history],
            key_fn=lambda p: "above_200" if p.above_sma200 else "below_200",
            include_labels={"above_200"},
        )
        below_segments = self._build_segments(
            [p for p in filtered if p.has_sufficient_history],
            key_fn=lambda p: "above_200" if p.above_sma200 else "below_200",
            include_labels={"below_200"},
        )

        dataset_meta = self._data_provider.get_last_dataset_meta() or {}

        return {
            "symbol": symbol,
            "indicator_start": indicator_start,
            "analysis_start": analysis_start,
            "analysis_end": analysis_end,
            "dataset": {
                "source_type": dataset_meta.get("source_type"),
                "dataset_id": dataset_meta.get("dataset_id"),
                "timeframe": dataset_meta.get("timeframe", "1d"),
                "dataset_signature": dataset_meta.get("data_signature"),
                "quality_status": dataset_meta.get("quality_status"),
            },
            "regime_counts": dict(regime_counts),
            "above_200_days": len(above_points),
            "below_200_days": len(below_points),
            "insufficient_history_days": int(regime_counts.get("insufficient_history", 0)),
            "above_200_return": round(self._compound_return(above_segments), 4),
            "below_200_return": round(self._compound_return(below_segments), 4),
            "daily_points": [
                {
                    "date": p.date,
                    "close": p.close,
                    "sma200": p.sma200,
                    "ema20": p.ema20,
                    "ema50": p.ema50,
                    "ema200": p.ema200,
                    "sma200_slope_5d": p.sma200_slope_5d,
                    "sma200_slope_20d": p.sma200_slope_20d,
                    "distance_from_sma200_pct": p.distance_from_sma200_pct,
                    "above_sma200": p.above_sma200,
                    "has_sufficient_history": p.has_sufficient_history,
                    "regime": p.regime,
                }
                for p in filtered
            ],
            "regime_segments": regime_segments,
            "above_200_segments": above_segments,
            "below_200_segments": below_segments,
        }

    def analyze_batch(
        self,
        symbols: list[str],
        indicator_start: date,
        analysis_start: date,
        analysis_end: date,
    ) -> dict:
        if not symbols:
            raise ValueError("symbols must not be empty")
        items = [self.analyze(s, indicator_start, analysis_start, analysis_end) for s in symbols]
        summary_counter = Counter()
        for item in items:
            summary_counter.update(item.get("regime_counts", {}))

        return {
            "indicator_start": indicator_start,
            "analysis_start": analysis_start,
            "analysis_end": analysis_end,
            "items": items,
            "summary": {
                "symbol_count": len(items),
                "above_200_days": sum(item.get("above_200_days", 0) for item in items),
                "below_200_days": sum(item.get("below_200_days", 0) for item in items),
                "insufficient_history_days": sum(item.get("insufficient_history_days", 0) for item in items),
                "avg_above_200_return": round(
                    mean([item.get("above_200_return", 0.0) for item in items]),
                    4,
                )
                if items
                else 0.0,
                "avg_below_200_return": round(
                    mean([item.get("below_200_return", 0.0) for item in items]),
                    4,
                )
                if items
                else 0.0,
                **{f"regime_{k}": v for k, v in dict(summary_counter).items()},
            },
        }

    def _build_segments(
        self,
        points: list[RegimePoint],
        key_fn,
        include_labels: set[str] | None = None,
    ) -> list[dict]:
        if not points:
            return []

        out: list[dict] = []
        current_label = key_fn(points[0])
        current_points = [points[0]]

        for point in points[1:]:
            point_label = key_fn(point)
            prev_date = date.fromisoformat(current_points[-1].date)
            cur_date = date.fromisoformat(point.date)
            contiguous = (cur_date - prev_date) <= timedelta(days=1)
            if point_label != current_label or not contiguous:
                if include_labels is None or current_label in include_labels:
                    out.append(self._to_segment(current_label, current_points))
                current_label = point_label
                current_points = [point]
            else:
                current_points.append(point)

        if include_labels is None or current_label in include_labels:
            out.append(self._to_segment(current_label, current_points))
        return out

    def _to_segment(self, label: str, points: list[RegimePoint]) -> dict:
        start_close = points[0].close
        end_close = points[-1].close
        segment_return = ((end_close - start_close) / max(start_close, 1e-9)) * 100
        distances = [p.distance_from_sma200_pct for p in points if p.distance_from_sma200_pct is not None]
        slopes = [p.sma200_slope_20d for p in points if p.sma200_slope_20d is not None]
        if slopes:
            slope_mean = mean(slopes)
            slope_state = "rising" if slope_mean > 0 else ("falling" if slope_mean < 0 else "flat")
        else:
            slope_state = "unknown"

        return {
            "label": label,
            "start_date": points[0].date,
            "end_date": points[-1].date,
            "days": len(points),
            "start_close": round(start_close, 6),
            "end_close": round(end_close, 6),
            "return_pct": round(segment_return, 4),
            "avg_distance_from_sma200_pct": round(mean(distances), 6) if distances else 0.0,
            "sma200_slope_state": slope_state,
        }

    def _compound_return(self, segments: list[dict]) -> float:
        if not segments:
            return 0.0
        compounded = 1.0
        for seg in segments:
            compounded *= 1 + (float(seg.get("return_pct", 0.0)) / 100)
        return (compounded - 1) * 100
