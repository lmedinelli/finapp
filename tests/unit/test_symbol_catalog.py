from app.services.symbol_catalog import SymbolCatalogService


def test_symbol_search_by_symbol_prefix() -> None:
    service = SymbolCatalogService()
    result = service.search("aap", limit=5)
    assert result
    assert result[0]["symbol"] == "AAPL"
    assert result[0]["asset_type"] == "stock"


def test_symbol_search_by_name() -> None:
    service = SymbolCatalogService()
    result = service.search("bitcoin", limit=5)
    assert result
    assert any(item["symbol"] == "BTC" for item in result)


def test_symbol_search_empty_query_returns_catalog_slice() -> None:
    service = SymbolCatalogService()
    result = service.search("", limit=3)
    assert len(result) == 3
