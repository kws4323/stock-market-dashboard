"""Auditable static snapshots. Credentials are never written to published data."""
import json
import os
import math
import hashlib
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
        self.ua = os.getenv("SEC_USER_AGENT") or "StockDashBoard/1.0 (https://github.com/kws4323/stock-market-dashboard; contact: https://github.com/kws4323/stock-market-dashboard/issues)"
        self.key = os.getenv("FMP_API_KEY", "")

    def get(self, url, sec=False):
        if sec:
            time.sleep(0.2)  # Well below SEC's 10 requests/second ceiling.
        req = urllib.request.Request(url, headers={"User-Agent": self.ua if sec else "StockDashboard/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read(20 * 1024 * 1024 + 1)
                if len(data) > 20 * 1024 * 1024:
                    raise ValueError("Provider document exceeds size limit")
                return data
        except Exception:
            # urllib exceptions can contain query credentials. Never log them.
            raise RuntimeError("Provider request failed; check access, quota and service status") from None

    def sec(self, url):
        # Accession directories are immutable; submissions lists must stay live.
        if url.startswith("https://www.sec.gov/Archives/edgar/data/"):
            cache = ROOT / "work/sec-cache" / (hashlib.sha256(url.encode()).hexdigest() + ".bin")
            if cache.exists():
                return cache.read_bytes()
            raw = self.get(url, True)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(raw)
            return raw
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
                     "discretion": fields.get("investmentDiscretion", ""), "other_manager": fields.get("otherManager", ""),
                     "value": float(fields["value"]), "shares": float(fields["sshPrnamt"])})
    if not rows:
        raise ValueError("No 13F information table rows")
    return rows


def aggregate(rows, mappings):
    if any(not math.isfinite(r[k]) or r[k] < 0 for r in rows for k in ("value", "shares")):
        raise ValueError("Invalid portfolio numbers")
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


def load_information_table(client, cik, filing):
    accession = filing["accessionNumber"]
    base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/'
    primary = filing.get("primaryDocument", "").split("/")[-1]
    if not primary:
        raise ValueError("Amended filing or original missing primary document metadata")
    header = ET.fromstring(client.sec(base + primary))
    fields = {e.tag.split("}")[-1]: (e.text or "").strip() for e in header.iter()}
    count = int(fields["tableEntryTotal"])
    total = float(fields["tableValueTotal"])
    listing = json.loads(client.sec(base + "index.json"))["directory"]["item"]
    rows = []
    for item in listing:
        name = item["name"]
        if name == primary or not name.lower().endswith(".xml"):
            continue
        raw = client.sec(base + name)
        root = ET.fromstring(raw)
        if root.tag.split("}")[-1] == "informationTable":
            rows.extend(parse_table(raw))
    if len(rows) != count or not math.isclose(sum(r["value"] for r in rows), total, abs_tol=max(1, count)):
        raise ValueError("Incomplete 13F table: entry/value totals disagree with SEC cover page")
    # Historical forms used thousands; normalize before combining amendments.
    if filing["filingDate"] < "2023-01-03":
        rows = [{**r, "value": r["value"] * 1000} for r in rows]
    return {"rows": rows, "amendment_type": fields.get("amendmentType", "").upper(),
            "source_url": base + accession + "-index.html", "filed_at": filing["filingDate"]}


def combine_filings(filings):
    rows, sources = [], []
    for filing in filings:
        kind = filing["amendment_type"]
        if not kind or kind == "RESTATEMENT":
            rows = filing["rows"]
        elif kind == "NEW HOLDINGS":
            identity = lambda r: tuple(r.get(k, "") for k in ("cusip", "class", "option", "unit", "discretion", "other_manager"))
            known = {identity(r) for r in rows}
            if any(identity(r) in known for r in filing["rows"]):
                raise ValueError("Overlapping new-holdings amendment requires review")
            rows = rows + filing["rows"]
        else:
            raise ValueError("Unknown amendment type; excluded from denominator")
        sources.append(filing["source_url"])
    return rows, sources


def institution(client, manager, mappings):
    cik = manager["cik"]
    data = json.loads(client.sec(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))
    recent = data["filings"]["recent"]
    def extract(block):
        return [{k: block[k][i] for k in ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument") if k in block}
                for i in range(len(block["form"])) if block["form"][i] in ("13F-HR", "13F-HR/A")]
    filings = extract(recent)
    for archive in sorted(data["filings"].get("files", []), key=lambda a:a.get("filingTo", ""), reverse=True)[:3]:
        if len({f["reportDate"] for f in filings if f["reportDate"]}) >= 2:
            break
        name = archive["name"]
        if not re.fullmatch(r"CIK\d+-submissions-\d+\.json", name):
            raise ValueError("Unexpected submissions archive name")
        filings.extend(extract(json.loads(client.sec("https://data.sec.gov/submissions/" + name))))
    periods = sorted({f["reportDate"] for f in filings if f["reportDate"]}, reverse=True)[:2]
    if len(periods) < 2:
        raise ValueError("Two reporting quarters unavailable in recent submissions")
    snapshots = []
    for period in periods:
        group = sorted([f for f in filings if f["reportDate"] == period], key=lambda f:(f["filingDate"], f["accessionNumber"]))
        if not group or group[0]["form"] != "13F-HR" or sum(f["form"] == "13F-HR" for f in group) != 1:
            raise ValueError("Original 13F filing unavailable or ambiguous")
        tables = [load_information_table(client, cik, filing) for filing in group]
        if any(f["form"].endswith("/A") and not t["amendment_type"] for f,t in zip(group,tables)):
            raise ValueError("Amended filing type unavailable")
        rows, sources = combine_filings(tables)
        snapshots.append({"period": period, "filed_at": tables[-1]["filed_at"], "source_url": tables[-1]["source_url"], "source_urls": sources, "holdings": aggregate(rows, mappings)})
    current, previous = snapshots
    # Share changes are only comparable across adjacent quarters.
    p, q = date.fromisoformat(current["period"]), date.fromisoformat(previous["period"])
    if (p.year * 4 + (p.month - 1) // 3) - (q.year * 4 + (q.month - 1) // 3) != 1:
        raise ValueError("Nonadjacent quarters")
    return {**manager, "period": current["period"], "previous_period": previous["period"], "filed_at": current["filed_at"], "source_url": current["source_url"], "source_urls":current["source_urls"], "previous_source_url": previous["source_url"], "holdings": changes(current["holdings"], previous["holdings"])}


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
    config = json.loads((ROOT / "config/tracking.json").read_text(encoding="utf-8"))
    if config.get("free_mode"):
        from free_sources import collect_free
        result = collect_free(Client(), config, previous)
    else:
        result = collect(Client(), config, previous)
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
