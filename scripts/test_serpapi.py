import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    from app.services.news import NewsService

    parser = argparse.ArgumentParser(
        description="Test SerpAPI news retrieval and sentiment scoring"
    )
    parser.add_argument("symbol", nargs="?", default="AAPL")
    parser.add_argument("--asset-type", default="stock", choices=["stock", "crypto", "etf"])
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    service = NewsService()
    if not service.settings.serpapi_api_key:
        print("SERPAPI_API_KEY is not configured. Set it in .env or shell environment.")
        return 1

    headlines = service.fetch_news(
        symbol=args.symbol,
        asset_type=args.asset_type,
        limit=args.limit,
    )
    sentiment = service.sentiment_summary(headlines)

    result = {
        "symbol": args.symbol.upper(),
        "asset_type": args.asset_type,
        "headlines_count": len(headlines),
        "sentiment": sentiment,
        "headlines": headlines,
    }
    if args.debug and not headlines:
        query = service._build_query(symbol=args.symbol, asset_type=args.asset_type)
        params = {
            "engine": "google_news",
            "q": query,
            "api_key": service.settings.serpapi_api_key,
            "num": args.limit,
            "hl": "en",
        }
        try:
            debug_response = httpx.get(
                service.settings.serpapi_endpoint,
                params=params,
                timeout=15.0,
            )
            result["debug_status_code"] = debug_response.status_code
            result["debug_payload"] = debug_response.json()
        except Exception as exc:  # pragma: no cover - debug path
            result["debug_error"] = str(exc)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
