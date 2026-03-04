from app.services.scan_the_market import ScanTheMarketService


def test_scan_the_market_compose_response(monkeypatch) -> None:
    service = ScanTheMarketService()

    monkeypatch.setattr(
        service,
        "_stock_candidates",
        lambda exchange_list, warnings: [("SOFI", "SoFi Technologies", "mock")],
    )
    monkeypatch.setattr(
        service,
        "_scan_stocks",
        lambda candidates, low_cap_max_usd, limit: [
            {
                "symbol": "SOFI",
                "name": "SoFi Technologies",
                "asset_type": "stock",
                "market_cap": 9_000_000_000.0,
                "price": 8.2,
                "change_pct": 1.1,
                "volume": 1_000_000.0,
                "momentum_30d": 12.0,
                "score": 2.5,
                "rationale": "mock",
                "source": "mock",
            }
        ],
    )
    monkeypatch.setattr(
        service,
        "_scan_crypto",
        lambda low_cap_max_usd, limit, warnings: ([], set()),
    )
    monkeypatch.setattr(service, "_collect_news_signals", lambda stocks, crypto: [])
    monkeypatch.setattr(
        service,
        "_theme_watchlist",
        lambda keyword, asset_type, category: [],
    )

    result = service.scan(
        low_cap_max_usd=10_000_000_000.0,
        stock_limit=5,
        crypto_limit=5,
        include_ipo=True,
        include_ico=True,
        include_news=True,
        exchanges=["NASDAQ"],
    )

    assert result["low_cap_max_usd"] == 10_000_000_000.0
    assert result["stock_opportunities"][0]["symbol"] == "SOFI"
    assert isinstance(result.get("warnings"), list)
    assert "mock" in result.get("data_sources", [])


def test_scan_crypto_coinmarketcap_parser(monkeypatch) -> None:
    service = ScanTheMarketService()
    service.settings.coinmarketcap_api_key = "test-key"
    monkeypatch.setattr(
        service,
        "_coinmarketcap_get",
        lambda path, params: {
            "data": [
                {
                    "symbol": "ARB",
                    "name": "Arbitrum",
                    "cmc_rank": 80,
                    "is_active": 1,
                    "quote": {
                        "USD": {
                            "market_cap": 1_200_000_000.0,
                            "price": 1.2,
                            "volume_24h": 150_000_000.0,
                            "percent_change_24h": 2.5,
                            "percent_change_7d": 5.0,
                            "percent_change_30d": 22.0,
                        }
                    },
                }
            ]
        },
    )
    warnings: list[str] = []
    rows = service._scan_crypto_coinmarketcap(
        low_cap_max_usd=2_000_000_000.0,
        limit=8,
        warnings=warnings,
    )
    assert rows
    assert rows[0]["symbol"] == "ARB"
    assert rows[0]["source"] == "coinmarketcap"
