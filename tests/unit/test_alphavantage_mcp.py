from types import SimpleNamespace

from app.services.alphavantage_mcp import AlphaVantageMCPService


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict:
        return self._payload


def test_global_quote_parsing(monkeypatch) -> None:
    service = AlphaVantageMCPService()
    service.settings = SimpleNamespace(
        alphavantage_api_key="test-key",
        alphavantage_mcp_url="https://mcp.alphavantage.co/mcp",
        alphavantage_timeout_seconds=10.0,
        alphavantage_daily_points=120,
        alphavantage_news_items=10,
    )

    payload = {
        "Global Quote": {
            "01. symbol": "AAPL",
            "05. price": "190.1200",
            "06. volume": "1200300",
            "07. latest trading day": "2026-03-02",
            "10. change percent": "1.45%",
        }
    }

    def fake_get(url: str, params: dict, timeout: float) -> DummyResponse:
        assert url == "https://mcp.alphavantage.co/mcp"
        assert params["function"] == "GLOBAL_QUOTE"
        assert params["apikey"] == "test-key"
        assert timeout == 10.0
        return DummyResponse(payload)

    monkeypatch.setattr("app.services.alphavantage_mcp.httpx.get", fake_get)
    result = service.get_global_quote("AAPL")
    assert result["symbol"] == "AAPL"
    assert result["price"] == 190.12
    assert result["change_percent"] == 1.45


def test_market_context_builds_trend(monkeypatch) -> None:
    service = AlphaVantageMCPService()
    service.settings = SimpleNamespace(
        alphavantage_api_key="test-key",
        alphavantage_mcp_url="https://mcp.alphavantage.co/mcp",
        alphavantage_timeout_seconds=10.0,
        alphavantage_daily_points=120,
        alphavantage_news_items=10,
    )

    def fake_request(function: str, **kwargs: str | int) -> dict:
        if function == "TIME_SERIES_DAILY":
            rows: dict[str, dict[str, str]] = {}
            for i in range(1, 61):
                price = 100 + i
                rows[f"2026-01-{i:02d}" if i <= 31 else f"2026-02-{i - 31:02d}"] = {
                    "1. open": str(price - 1),
                    "2. high": str(price + 1),
                    "3. low": str(price - 2),
                    "4. close": str(price),
                    "5. volume": "1000",
                }
            return {"Time Series (Daily)": rows}
        if function == "GLOBAL_QUOTE":
            return {
                "Global Quote": {
                    "01. symbol": "AAPL",
                    "05. price": "160",
                    "10. change percent": "0.5%",
                }
            }
        if function == "NEWS_SENTIMENT":
            return {"feed": []}
        return {}

    monkeypatch.setattr(service, "_request", fake_request)
    result = service.get_market_context("AAPL")
    assert result["symbol"] == "AAPL"
    assert result["trend"]["direction"] == "uptrend"
    assert len(result["candles"]) == 60


def test_market_context_parses_alternative_daily_key(monkeypatch) -> None:
    service = AlphaVantageMCPService()
    service.settings = SimpleNamespace(
        alphavantage_api_key="test-key",
        alphavantage_mcp_url="https://mcp.alphavantage.co/mcp",
        alphavantage_timeout_seconds=10.0,
        alphavantage_daily_points=120,
        alphavantage_news_items=10,
    )

    def fake_request(function: str, **kwargs: str | int) -> dict:
        if function == "TIME_SERIES_DAILY":
            return {
                "result": {
                    "time_series_daily": {
                        "2026-03-01": {
                            "1. open": "100",
                            "2. high": "101",
                            "3. low": "99",
                            "4. close": "100.5",
                            "5. volume": "1200",
                        },
                        "2026-03-02": {
                            "1. open": "101",
                            "2. high": "102",
                            "3. low": "100",
                            "4. close": "101.5",
                            "5. volume": "1300",
                        },
                    }
                }
            }
        if function == "GLOBAL_QUOTE":
            return {"Global Quote": {"01. symbol": "AAPL", "05. price": "101.5"}}
        if function == "NEWS_SENTIMENT":
            return {"feed": []}
        return {}

    monkeypatch.setattr(service, "_request", fake_request)
    result = service.get_market_context("AAPL")
    assert len(result["candles"]) == 2
    assert result["candles"][-1]["close"] == 101.5


def test_symbol_normalization_for_crypto_pair() -> None:
    service = AlphaVantageMCPService()
    assert service._normalize_symbol("btc-usd") == "BTC"
    assert service._normalize_symbol("appl") == "AAPL"


def test_request_fallback_to_rest(monkeypatch) -> None:
    service = AlphaVantageMCPService()

    monkeypatch.setattr(service, "_request_mcp", lambda function, **kwargs: {"Note": "try again"})
    monkeypatch.setattr(
        service,
        "_request_rest",
        lambda function, **kwargs: {"Global Quote": {"01. symbol": "AAPL", "05. price": "150"}},
    )

    payload = service._request("GLOBAL_QUOTE", symbol="AAPL")
    assert "Global Quote" in payload


def test_market_context_exposes_warning_without_api_key() -> None:
    service = AlphaVantageMCPService()
    service.settings = SimpleNamespace(
        alphavantage_api_key="",
        alphavantage_mcp_url="https://mcp.alphavantage.co/mcp",
        alphavantage_rest_url="https://www.alphavantage.co/query",
        alphavantage_timeout_seconds=10.0,
        alphavantage_daily_points=120,
        alphavantage_news_items=10,
    )

    result = service.get_market_context("AAPL")
    warnings = result["warnings"]
    assert warnings
    assert any("API key is missing" in item for item in warnings)
