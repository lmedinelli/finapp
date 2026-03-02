import pandas as pd
import pytest

from app.services.analytics import AnalyticsService


class DummyAnalytics(AnalyticsService):
    def __init__(self, frame: pd.DataFrame):
        self._frame = frame

    def load_series(self, symbol: str) -> pd.DataFrame:
        return self._frame


def test_compute_returns_expected_keys() -> None:
    rows = 80
    frame = pd.DataFrame(
        {
            "close": [100 + i * 0.5 for i in range(rows)],
            "timestamp": pd.date_range("2025-01-01", periods=rows, freq="D"),
        }
    )
    service = DummyAnalytics(frame)
    result = service.compute("AAPL")
    assert set(result.keys()) == {
        "symbol",
        "latest_close",
        "sma_20",
        "sma_50",
        "volatility_30d",
        "momentum_30d",
        "signal",
    }


def test_compute_requires_minimum_data() -> None:
    frame = pd.DataFrame({"close": [100, 101], "timestamp": pd.date_range("2025-01-01", periods=2, freq="D")})
    service = DummyAnalytics(frame)
    with pytest.raises(ValueError):
        service.compute("AAPL")
