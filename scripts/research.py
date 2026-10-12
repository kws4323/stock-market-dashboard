"""Auditable static snapshots. Credentials are never written to published data."""
import json
import os
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


class Client:
    def __init__(self):
        self.ua = os.getenv("SEC_USER_AGENT", "")
        self.key = os.getenv("FMP_API_KEY", "")

    def get(self, url, sec=False):
        if sec:
            time.sleep(0.2)  # Well below SEC's 10 requests/second ceiling.
        req = urllib.request.Request(url, headers={"User-Agent": self.ua if sec else "StockDashboard/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except Exception:
            # urllib exceptions can contain query credentials. Never log them.
            raise RuntimeError("Provider request failed; check access, quota and service status") from None

    def sec(self, url):
        return self.get(url, True)

    def fmp(self, endpoint, **params):
        params["apikey"] = self.key
        result = json.loads(self.get("https://financialmodelingprep.com/stable/" + endpoint + "?" + urllib.parse.urlencode(params)))
        if not isinstance(result, list):
            raise ValueError("Unexpected provider response")
        return result


def parse_table(raw):
    root = ET.fromstring(raw)
    rows = []
    for el in root.iter():
        if el.tag.split("}")[-1] != "infoTable":
            continue
        fields = {x.tag.split("}")[-1]: (x.text or "").strip() for x in el.iter()}
        rows.append({"cusip": fields["cusip"].upper(), "issuer": fields["nameOfIssuer"],
                     "class": fields.get("titleOfClass", ""), "option": fields.get("putCall", ""),
                     "unit": fields.get("sshPrnamtType", ""),
                     "value": float(fields["value"]), "shares": float(fields["sshPrnamt"])})
    if not rows:
        raise ValueError("No 13F information table rows")
    return rows


def aggregate(rows, mappings):
    total = sum(r["value"] for r in rows)
    if total <= 0:
        raise ValueError("Invalid portfolio value")
    holdings = {}
    for r in rows:
        # Options are separate exposures, never silently counted as common stock.
        if r["option"] or r["unit"] != "SH":
            continue
        key = r["cusip"]
        h = holdings.setdefault(key, {"cusip": key, "symbol": mappings.get(key), "issuer": r["issuer"], "value": 0, "shares": 0})
        h["value"] += r["value"]
        h["shares"] += r["shares"]
    for h in holdings.values():
        h["weight_pct"] = round(h["value"] / total * 100, 4)
    return holdings


def changes(current, previous):
    result = []
    for key in sorted(current.keys() | previous.keys()):
        a, b = current.get(key), previous.get(key)
        delta = (a or {}).get("shares", 0) - (b or {}).get("shares", 0)
        result.append({**(a or b), "shares": a["shares"] if a else 0,
                       "weight_pct": a["weight_pct"] if a else 0,
                       "share_change": delta,
                       "change": "new" if not b else "exit" if not a else "increase" if delta > 0 else "decrease" if delta < 0 else "unchanged"})
    return result


def institution(client, manager, mappings):
    cik = manager["cik"]
    data = json.loads(client.sec(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))
    recent = data["filings"]["recent"]
    filings = [{k: recent[k][i] for k in ("form", "reportDate", "filingDate", "accessionNumber")} for i in range(len(recent["form"])) if recent["form"][i] in ("13F-HR", "13F-HR/A")]
    periods = sorted({f["reportDate"] for f in filings if f["reportDate"]}, reverse=True)[:2]
    if len(periods) < 2:
        raise ValueError("Two reporting quarters unavailable in recent submissions")
    snapshots = []
    for period in periods:
        group = [f for f in filings if f["reportDate"] == period]
        if any(f["form"].endswith("/A") for f in group):
            raise ValueError("Amended filing requires reconciliation; excluded from denominator")
        filing = max(group, key=lambda f: f["filingDate"])
        base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{filing["accessionNumber"].replace("-", "")}/'
        listing = json.loads(client.sec(base + "index.json"))["directory"]["item"]
        rows = []
        for item in listing:
            name = item["name"]
            if not name.lower().endswith(".xml"):
                continue
            raw = client.sec(base + name)
            if b"infotable" in raw.lower():
                rows.extend(parse_table(raw))
        snapshots.append({"period": period, "filed_at": filing["filingDate"], "source_url": base + filing["accessionNumber"] + "-index.html", "holdings": aggregate(rows, mappings)})
    current, previous = snapshots
    # Share changes are only comparable across adjacent quarters.
    p, q = date.fromisoformat(current["period"]), date.fromisoformat(previous["period"])
    if (p.year * 4 + (p.month - 1) // 3) - (q.year * 4 + (q.month - 1) // 3) != 1:
        raise ValueError("Nonadjacent quarters")
    return {**manager, "period": current["period"], "previous_period": previous["period"], "filed_at": current["filed_at"], "source_url": current["source_url"], "previous_source_url": previous["source_url"], "holdings": changes(current["holdings"], previous["holdings"])}


def news(rows):
    result, seen = [], set()
    for r in rows:
        url = r.get("url", "")
        if not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        title = re.sub(r"<[^>]+>", "", r.get("title", ""))
        # No generated claims or republished article bodies. A headline digest is explicit.
        result.append({"title": title, "url": url, "publisher": r.get("publisher") or r.get("site"), "published_at": r.get("publishedDate"), "symbol": r.get("symbol"), "summary_method": "headline_only", "impact_tag": next((label for word, label in (("rate", "금리"), ("fed", "통화정책"), ("inflation", "물가"), ("tariff", "관세"), ("oil", "에너지"), ("earnings", "실적")) if word in title.lower()), "시장 일반")})
    return result


def ranked(rows, country, limit):
    # Rank company-level eligible local primary shares, excluding ETFs/funds/ADRs.
    exchanges = {"US": {"NASDAQ", "NYSE", "AMEX"}, "KR": {"KSC", "KOE", "KOSPI", "KOSDAQ"}}[country]
    eligible = [r for r in rows if r.get("country") == country and r.get("exchangeShortName") in exchanges and not r.get("isEtf") and not r.get("isFund") and float(r.get("marketCap") or 0) > 0]
    seen, output = set(), []
    for r in sorted(eligible, key=lambda r: float(r["marketCap"]), reverse=True):
        identity = r.get("companyName") or r["symbol"]
        if identity in seen:
            continue
        seen.add(identity)
        output.append({"symbol": r["symbol"], "name": identity, "market_cap": r["marketCap"], "rank": len(output) + 1})
    return output[:limit]


def calendar(client):
    # Match the user's schedule even when the Actions runner uses UTC.
    start = datetime.now(timezone(timedelta(hours=9))).date()
    end = start + timedelta(days=90)
    events = client.fmp("earnings-calendar", **{"from": start.isoformat(), "to": end.isoformat()})
    output = {"from": start.isoformat(), "to": end.isoformat(), "ranked_at": now(), "countries": {}}
    for country, target in (("KR", 100), ("US", 300)):
        rows = client.fmp("company-screener", country=country, isEtf="false", isFund="false", isActivelyTrading="true", limit=10000)
        if len(rows) >= 10000:
            raise ValueError("Screener truncated; cannot establish market-cap rank")
        universe = ranked(rows, country, target)
        symbols = {r["symbol"] for r in universe}
        filtered = [{"symbol": r["symbol"], "date": r["date"], "eps_estimated": r.get("epsEstimated"), "revenue_estimated": r.get("revenueEstimated"), "status": "provider_schedule_unconfirmed"} for r in events if r.get("symbol") in symbols and start.isoformat() <= r.get("date", "") <= end.isoformat()]
        output["countries"][country] = {"target": target, "covered": len(universe), "coverage_complete": len(universe) == target, "universe": universe, "events": sorted(filtered, key=lambda r: (r["date"], r["symbol"])), "missing_schedule": sorted(symbols - {r["symbol"] for r in filtered})}
    return output


def collect(client, config, previous=None):
    result = {"attempted_at": now(), "sections": {}}
    def section(name, enabled, fn):
        if not enabled:
            result["sections"][name] = {"status": "not_configured", "data": None}
            return
        try:
            result["sections"][name] = {"status": "ok", "updated_at": now(), "data": fn()}
        except Exception as exc:
            old = (previous or {}).get("sections", {}).get(name, {})
            result["sections"][name] = {"status": "stale" if old.get("data") is not None else "error", "updated_at": old.get("updated_at"), "data": old.get("data"), "error": str(exc) if isinstance(exc, ValueError) else "Provider unavailable; check access/quota"}
    section("institutions", bool(client.ua), lambda: [safe_manager(client, m, config["cusips"]) for m in config["institutions"]])
    licensed = bool(client.key) and os.getenv("FMP_PUBLIC_REDISTRIBUTION") == "true"
    section("ptr", licensed, lambda: [{**r, "chamber": chamber} for chamber in ("senate", "house") for r in client.fmp(chamber + "-latest", page=0, limit=100)])
    section("market_news", licensed, lambda: news(client.fmp("news/general-latest", page=0, limit=30)))
    section("stock_news", licensed, lambda: news(client.fmp("news/stock", symbols=",".join(config["news_symbols"]), limit=100)))
    section("calendar", licensed, lambda: calendar(client))
    return result


def safe_manager(client, manager, mappings):
    try:
        return {"status": "ok", **institution(client, manager, mappings)}
    except Exception as exc:
        return {**manager, "status": "error", "error": str(exc) if isinstance(exc, ValueError) else "SEC unavailable or invalid filing"}


if __name__ == "__main__":
    path = ROOT / "data/research.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    result = collect(Client(), json.loads((ROOT / "config/tracking.json").read_text(encoding="utf-8")), previous)
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
