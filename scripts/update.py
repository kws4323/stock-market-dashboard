import json
import os
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

SYMBOLS = {
    "KOSPI": "^KS11", "KOSDAQ": "^KQ11", "S&P 500": "^GSPC",
    "NASDAQ Composite": "^IXIC", "Russell 2000": "^RUT",
    "Dow Jones": "^DJI", "WTI": "CL=F", "Gold": "GC=F",
    "US 10Y Yield": "^TNX", "USD/KRW": "KRW=X",
    "Dollar Index": "DX-Y.NYB", "VIX": "^VIX"
}
out = Path("data/markets.json")
previous = {}
if out.exists():
    try:
        previous = {x["name"]: x for x in json.loads(out.read_text())["markets"]}
    except (ValueError, KeyError):
        pass
items = []
for name, symbol in SYMBOLS.items():
    try:
        frame = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
        values = [{"date": str(t.date()), "close": round(float(row["Close"]), 4)}
                  for t, row in frame.iterrows() if not __import__("math").isnan(float(row["Close"]))]
        if not values:
            raise ValueError("empty prices")
        latest = values[-1]["close"]
        old = values[-2]["close"] if len(values) > 1 else None
        items.append({"name": name, "symbol": symbol, "close": latest,
                      "change_pct": round((latest / old - 1) * 100, 2) if old else None,
                      "history": values, "source": "Yahoo Finance (unofficial)",
                      "status": "ok", "collected_at": datetime.now(timezone.utc).isoformat()})
        print(name, latest)
    except Exception as exc:
        print(f"WARNING {name}: {exc}")
        items.append({**previous.get(name, {"name": name, "symbol": symbol,
                     "close": None, "change_pct": None, "history": []}), "status": "stale"})
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(),
                           "markets": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
