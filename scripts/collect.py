"""Collect actual Yahoo Finance quotes for a static GitHub Pages snapshot."""
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]

def finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None

def collect(symbol):
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="1y", interval="1d", auto_adjust=False, raise_errors=True)
    if history.empty:
        raise ValueError("Empty price history")
    meta = ticker.get_history_metadata() or {}
    points = []
    for index, row in history.iterrows():
        price = finite(row.get("Close"))
        if price is not None:
            points.append({"t": int(index.timestamp() * 1000), "p": price, "v": finite(row.get("Volume"))})
    if len(points) < 2:
        raise ValueError("Insufficient price history")
    price = finite(meta.get("regularMarketPrice")) or points[-1]["p"]
    previous = finite(meta.get("previousClose")) or finite(meta.get("regularMarketPreviousClose")) or points[-2]["p"]
    return {"symbol": symbol, "source": "Yahoo Finance via yfinance", "retrieved": datetime.now(timezone.utc).isoformat(),
            "meta": {"regularMarketPrice": price, "previousClose": previous,
                     "regularMarketTime": meta.get("regularMarketTime") or points[-1]["t"] // 1000,
                     "currency": meta.get("currency", "")}, "points": points}

def main():
    config = json.loads((ROOT / "symbols.json").read_text(encoding="utf-8"))
    quotes, failures = {}, []
    for item in config:
        symbol = item["symbol"]
        for attempt in range(2):
            try:
                quotes[symbol] = collect(symbol)
                print(f"OK {symbol}: {len(quotes[symbol]['points'])} points", flush=True)
                break
            except Exception as exc:
                if attempt == 0:
                    time.sleep(2)
                else:
                    quotes[symbol] = {"error": "시세 제공처에서 데이터를 받지 못했습니다."}
                    failures.append(symbol)
                    print(f"FAILED {symbol}: {type(exc).__name__}", flush=True)
    if len(failures) == len(config):
        raise RuntimeError("All providers failed. Keep the previous published site; do not publish an empty snapshot.")
    result = {"schemaVersion": 1, "generatedAt": datetime.now(timezone.utc).isoformat(),
              "source": "Yahoo Finance via yfinance", "catalog": config, "quotes": quotes, "failedSymbols": failures}
    target = ROOT / "site" / "data" / "market.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    print(f"Collected {len(config)-len(failures)}/{len(config)} symbols")

if __name__ == "__main__":
    main()
