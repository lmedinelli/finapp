import argparse

from app.services.market_data import MarketDataService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest historical prices for one symbol")
    parser.add_argument("symbol", nargs="?", default="AAPL")
    parser.add_argument("--asset-type", default="stock")
    args = parser.parse_args()

    service = MarketDataService()
    result = service.ingest(symbol=args.symbol, asset_type=args.asset_type)
    print(result)


if __name__ == "__main__":
    main()
