import httpx

from app.services.chart_img import ChartImgService


def test_map_studies_from_metrics() -> None:
    mapped = ChartImgService._map_studies(["sma_20", "ema_50", "macd", "volume", "rsi_14"])
    names = [str(item.get("name", "")) for item in mapped]
    assert "Moving Average" in names
    assert "Moving Average Exponential" in names
    assert "Moving Average Convergence Divergence" in names
    assert "Volume" in names
    assert "Relative Strength Index" in names


def test_resolve_tradingview_symbol_fallback() -> None:
    service = ChartImgService()
    assert service.resolve_tradingview_symbol("AAPL", "stock") == "NASDAQ:AAPL"
    assert service.resolve_tradingview_symbol("BTC", "crypto") == "BINANCE:BTCUSDT"


def test_chart_img_list_exchanges(monkeypatch) -> None:
    service = ChartImgService()
    service.settings.chart_img_enforce_limits = False

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, str]]:
            return [{"name": "NASDAQ", "code": "NASDAQ"}]

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: MockResponse())
    service.settings.chart_img_api_key = "test-key"
    rows = service.list_exchanges()
    assert rows[0]["code"] == "NASDAQ"


def test_chart_img_search_symbols(monkeypatch) -> None:
    service = ChartImgService()
    service.settings.chart_img_enforce_limits = False

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, str]]:
            return [
                {
                    "symbol": "AAPL",
                    "exchange": "NASDAQ",
                    "description": "Apple Inc",
                    "full_symbol": "NASDAQ:AAPL",
                }
            ]

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: MockResponse())
    service.settings.chart_img_api_key = "test-key"
    rows = service.search_symbols("AAPL")
    assert rows[0]["full_symbol"] == "NASDAQ:AAPL"


def test_chart_img_list_symbols(monkeypatch) -> None:
    service = ChartImgService()
    service.settings.chart_img_enforce_limits = False

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, str]]:
            return [
                {
                    "symbol": "AAPL",
                    "description": "Apple Inc",
                    "exchange": "NASDAQ",
                    "full_symbol": "NASDAQ:AAPL",
                }
            ]

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: MockResponse())
    service.settings.chart_img_api_key = "test-key"
    rows = service.list_symbols("NASDAQ")
    assert rows[0]["symbol"] == "AAPL"


def test_chart_img_render_candle_image(monkeypatch) -> None:
    service = ChartImgService()
    service.settings.chart_img_api_key = "test-key"
    service.settings.chart_img_enforce_limits = False
    monkeypatch.setattr(
        service,
        "resolve_tradingview_symbol",
        lambda symbol, asset_type, exchange=None: "NASDAQ:AAPL",
    )

    class MockResponse:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = b"fake-image-bytes"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: MockResponse())
    payload = service.render_candle_image(
        symbol="AAPL",
        asset_type="stock",
        interval="1D",
        studies=["sma_20", "rsi_14"],
    )
    assert payload["symbol"] == "AAPL"
    assert payload["tradingview_symbol"] == "NASDAQ:AAPL"
    assert payload["source"] == "chart-img:v2:/v2/tradingview/advanced-chart"


def test_chart_img_render_candle_image_applies_resolution_fallback(monkeypatch) -> None:
    service = ChartImgService()
    service.settings.chart_img_api_key = "test-key"
    service.settings.chart_img_enforce_limits = False
    service.settings.chart_img_max_width = 4000
    service.settings.chart_img_max_height = 2200
    monkeypatch.setattr(
        service,
        "resolve_tradingview_symbol",
        lambda symbol, asset_type, exchange=None: "NASDAQ:AAPL",
    )

    class MockResponse:
        def __init__(
            self,
            *,
            status_code: int,
            headers: dict[str, str],
            content: bytes = b"",
            json_data: dict[str, str] | None = None,
        ) -> None:
            self.status_code = status_code
            self.headers = headers
            self.content = content
            self._json_data = json_data or {}
            self.text = str(self._json_data)

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("POST", "https://api.chart-img.com/v2/tradingview/advanced-chart")
                raise httpx.HTTPStatusError("error", request=request, response=self)

        def json(self) -> dict[str, str]:
            return self._json_data

    responses = [
        MockResponse(
            status_code=403,
            headers={"content-type": "application/json"},
            json_data={"message": "Exceed Max Usage Resolution Limit (800x600)"},
        ),
        MockResponse(
            status_code=200,
            headers={"content-type": "image/png"},
            content=b"image-bytes",
        ),
    ]
    captured_payloads: list[dict[str, object]] = []

    def mock_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_payloads.append(dict(kwargs.get("json", {})))
        return responses.pop(0)

    monkeypatch.setattr("httpx.post", mock_post)

    payload = service.render_candle_image(
        symbol="AAPL",
        asset_type="stock",
        interval="1D",
        width=1400,
        height=720,
        studies=["sma_20"],
    )

    assert len(captured_payloads) == 2
    assert captured_payloads[0]["width"] == 1400
    assert captured_payloads[0]["height"] == 720
    assert captured_payloads[1]["width"] == 800
    assert captured_payloads[1]["height"] == 600
    assert payload["width"] == 800
    assert payload["height"] == 600


def test_chart_img_render_candle_image_forces_v2_even_if_v1_configured(monkeypatch) -> None:
    service = ChartImgService()
    service.settings.chart_img_api_key = "test-key"
    service.settings.chart_img_enforce_limits = False
    service.settings.chart_img_api_version = "v1"
    service.settings.chart_img_v2_advanced_chart_path = "/v2/tradingview/advanced-chart"
    monkeypatch.setattr(
        service,
        "resolve_tradingview_symbol",
        lambda symbol, asset_type, exchange=None: "NASDAQ:AAPL",
    )
    called_urls: list[str] = []

    class MockResponse:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = b"fake-image-bytes"

        def raise_for_status(self) -> None:
            return None

    def mock_post(url: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        called_urls.append(url)
        return MockResponse()

    monkeypatch.setattr("httpx.post", mock_post)
    payload = service.render_candle_image(symbol="AAPL", asset_type="stock")
    assert called_urls
    assert called_urls[0].endswith("/v2/tradingview/advanced-chart")
    assert payload["source"] == "chart-img:v2:/v2/tradingview/advanced-chart"


def test_chart_img_render_candle_image_forces_v2_even_if_v3_configured(monkeypatch) -> None:
    service = ChartImgService()
    service.settings.chart_img_api_key = "test-key"
    service.settings.chart_img_enforce_limits = False
    service.settings.chart_img_api_version = "v3"
    service.settings.chart_img_v2_advanced_chart_path = "/v2/tradingview/advanced-chart"
    monkeypatch.setattr(
        service,
        "resolve_tradingview_symbol",
        lambda symbol, asset_type, exchange=None: "NASDAQ:AAPL",
    )
    called_urls: list[str] = []

    class MockResponse:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = b"fake-image-bytes"

        def raise_for_status(self) -> None:
            return None

    def mock_post(url: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        called_urls.append(url)
        return MockResponse()

    monkeypatch.setattr("httpx.post", mock_post)
    payload = service.render_candle_image(symbol="AAPL", asset_type="stock")
    assert called_urls
    assert called_urls[0].endswith("/v2/tradingview/advanced-chart")
    assert payload["source"] == "chart-img:v2:/v2/tradingview/advanced-chart"
