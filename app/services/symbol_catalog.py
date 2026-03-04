from __future__ import annotations

CATALOG: list[dict[str, str]] = [
    {"symbol": "AAPL", "name": "Apple Inc.", "asset_type": "stock"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "asset_type": "stock"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. Class A", "asset_type": "stock"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "asset_type": "stock"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "asset_type": "stock"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "asset_type": "stock"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "asset_type": "stock"},
    {"symbol": "BRK.B", "name": "Berkshire Hathaway Inc. Class B", "asset_type": "stock"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "asset_type": "stock"},
    {"symbol": "V", "name": "Visa Inc.", "asset_type": "stock"},
    {"symbol": "MA", "name": "Mastercard Incorporated", "asset_type": "stock"},
    {"symbol": "UNH", "name": "UnitedHealth Group Incorporated", "asset_type": "stock"},
    {"symbol": "XOM", "name": "Exxon Mobil Corporation", "asset_type": "stock"},
    {"symbol": "WMT", "name": "Walmart Inc.", "asset_type": "stock"},
    {"symbol": "PG", "name": "Procter & Gamble Co.", "asset_type": "stock"},
    {"symbol": "DIS", "name": "The Walt Disney Company", "asset_type": "stock"},
    {"symbol": "NFLX", "name": "Netflix Inc.", "asset_type": "stock"},
    {"symbol": "AMD", "name": "Advanced Micro Devices Inc.", "asset_type": "stock"},
    {"symbol": "BABA", "name": "Alibaba Group Holding Limited", "asset_type": "stock"},
    {"symbol": "BAC", "name": "Bank of America Corporation", "asset_type": "stock"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "asset_type": "etf"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "asset_type": "etf"},
    {"symbol": "DIA", "name": "SPDR Dow Jones Industrial Average ETF Trust", "asset_type": "etf"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "asset_type": "etf"},
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "asset_type": "etf"},
    {"symbol": "VOO", "name": "Vanguard S&P 500 ETF", "asset_type": "etf"},
    {"symbol": "ARKK", "name": "ARK Innovation ETF", "asset_type": "etf"},
    {"symbol": "BTC", "name": "Bitcoin", "asset_type": "crypto"},
    {"symbol": "ETH", "name": "Ethereum", "asset_type": "crypto"},
    {"symbol": "SOL", "name": "Solana", "asset_type": "crypto"},
    {"symbol": "XRP", "name": "XRP", "asset_type": "crypto"},
    {"symbol": "BNB", "name": "BNB", "asset_type": "crypto"},
    {"symbol": "ADA", "name": "Cardano", "asset_type": "crypto"},
    {"symbol": "DOGE", "name": "Dogecoin", "asset_type": "crypto"},
    {"symbol": "AVAX", "name": "Avalanche", "asset_type": "crypto"},
    {"symbol": "DOT", "name": "Polkadot", "asset_type": "crypto"},
    {"symbol": "LINK", "name": "Chainlink", "asset_type": "crypto"},
]


class SymbolCatalogService:
    def search(self, query: str, limit: int = 12) -> list[dict[str, str]]:
        max_items = max(1, min(limit, 300))
        term = query.strip().lower()
        if not term:
            sorted_catalog = sorted(CATALOG, key=lambda item: item["symbol"])
            return [dict(item) for item in sorted_catalog[:max_items]]

        scored: list[tuple[int, str, dict[str, str]]] = []
        for item in CATALOG:
            symbol = item["symbol"].lower()
            name = item["name"].lower()

            score = self._score_match(term=term, symbol=symbol, name=name)
            if score is None:
                continue
            scored.append((score, item["symbol"], item))

        scored.sort(key=lambda row: (row[0], row[1]))
        return [dict(item) for _, _, item in scored[:max_items]]

    @staticmethod
    def _score_match(term: str, symbol: str, name: str) -> int | None:
        if term == symbol:
            return 0
        if symbol.startswith(term):
            return 1
        if term in symbol:
            return 2
        if name.startswith(term):
            return 3
        if term in name:
            return 4
        return None
