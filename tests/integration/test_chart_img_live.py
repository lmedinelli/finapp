import base64
import os

import pytest

from app.services.chart_img import ChartImgService


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_CHART_IMG_TESTS", "0") != "1",
    reason="Set RUN_LIVE_CHART_IMG_TESTS=1 to run live Chart-IMG checks.",
)
def test_chart_img_live_render_and_validate_image() -> None:
    service = ChartImgService()
    if not service.settings.chart_img_api_key:
        pytest.skip("CHART_IMG_API_KEY is required for live Chart-IMG tests.")

    try:
        payload = service.render_candle_image(
            symbol="AAPL",
            asset_type="stock",
            interval="1D",
            studies=["sma_20", "ema_50", "rsi_14", "macd", "volume"],
        )
    except ValueError as exc:
        message = str(exc).lower()
        if (
            "nodename nor servname" in message
            or "connecterror" in message
            or "limit exceeded" in message
            or "exceed max usage resolution limit" in message
            or "too many requests" in message
        ):
            pytest.skip(
                "Live Chart-IMG endpoint not usable in this environment "
                "(network or account limit)."
            )
        raise

    assert payload["tradingview_symbol"]
    assert payload["content_type"].startswith("image/")
    raw_bytes = base64.b64decode(payload["image_base64"])
    assert len(raw_bytes) > 100
