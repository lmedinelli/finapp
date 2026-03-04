from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_candle_image_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.chart_img_service,
        "render_candle_image",
        lambda symbol, asset_type, interval, theme, width, height, studies, exchange: {
            "symbol": symbol,
            "asset_type": asset_type,
            "tradingview_symbol": "NASDAQ:AAPL",
            "interval": interval,
            "theme": theme,
            "width": width,
            "height": height,
            "studies_requested": studies,
            "studies_applied": ["Moving Average"],
            "content_type": "image/png",
            "image_base64": "ZmFrZV9pbWFnZQ==",
            "source": "chart-img:v2:advanced-chart",
        },
    )

    response = client.get(
        "/v1/market/candle-image/AAPL",
        params={
            "asset_type": "stock",
            "interval": "1D",
            "studies": "sma_20,macd,volume",
            "theme": "dark",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tradingview_symbol"] == "NASDAQ:AAPL"
    assert body["content_type"] == "image/png"
    assert body["image_base64"] == "ZmFrZV9pbWFnZQ=="
