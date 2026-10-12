"""No subscription keys. Original sources and honest partial-coverage metadata."""
import csv
import html
import io
import json
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

try:
    from .research import ROOT, now, institution
except ImportError:
    from research import ROOT, now, institution

KST = timezone(timedelta(hours=9))


def text(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value or ""))).strip()


def iso_date(value):
    try:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date().isoformat()
    except (ValueError, AttributeError):
        return None


def feed_time(value):
    try:
        d = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    # An unknown timezone must not be silently assumed to be UTC.
    return d.astimezone(timezone.utc).isoformat() if d.tzinfo else None


def topic_for(title, default="기업 발표"):
    for pattern, label in ((r"\b(inflation|pce|cpi)\b", "물가"), (r"\b(gdp|trade deficit|income|consumption)\b", "경제지표"),
                           (r"\b(fomc|federal funds|interest rates?)\b", "통화정책"), (r"\b(earnings|financial results|quarterly results)\b", "실적"),
                           (r"\b(tariffs?|trade policy)\b", "관세"), (r"\b(oil|energy)\b", "에너지"), (r"\b(ai|chips?|semiconductors?)\b", "AI·반도체")):
        if re.search(pattern, title, re.I):
            return label
    return default


def parse_feed(raw, source, cutoff):
    root = ET.fromstring(raw)
    result = []
    for item in root.iter():
        if item.tag.split("}")[-1] not in ("item", "entry"):
            continue
        fields = {}
        link = ""
        for child in item:
            key = child.tag.split("}")[-1]
            fields.setdefault(key, child.text or "")
            if key == "link" and child.get("rel", "alternate") == "alternate":
                link = child.get("href") or child.text or ""
        published = feed_time(fields.get("pubDate") or fields.get("published") or fields.get("updated") or fields.get("modDate"))
        if not published or datetime.fromisoformat(published) < cutoff:
            continue
        link = link.strip()
        if urlparse(link).scheme != "https" or not urlparse(link).hostname:
            continue
        title = text(fields.get("title"))
        if not title:
            continue
        # Short syndicated lead, never an invented full-text/AI summary.
        title = " ".join(title.split()[:25])
        lead = text(fields.get("description") or fields.get("summary") or fields.get("content"))
        if "appeared first on" in lead.lower() or lead.casefold() == title.casefold():
            lead = ""
        remaining = max(0, 25 - len(title.split()))
        lead = " ".join(lead.split()[:remaining])[:180].rsplit(" ", 1)[0] if len(lead) > 180 else " ".join(lead.split()[:remaining])
        topic = topic_for(title, source.get("default_topic", "기업 발표"))
        result.append({"title": title, "summary": lead or None, "summary_method": "official_feed_excerpt" if lead else "headline_only",
                       "url": link, "publisher": source["publisher"], "published_at": published,
                       "symbol": source.get("symbol"), "impact_tag": topic, "source_type": "official_rss",
                       "watch_point": {"통화정책":"확인 항목: 정책금리·채권금리·환율", "물가":"확인 항목: 물가 수치·통화정책 전망", "경제지표":"확인 항목: 경기·소비·무역 수치", "실적":"확인 항목: 실적·가이던스", "AI·반도체":"확인 항목: 제품·투자·수요"}.get(topic, "확인 항목: 발표 내용·관련 기업")})
    return result


def collect_feeds(client, settings, previous):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    old = (previous or {}).get("sections", {})
    old_rows = (old.get("market_news", {}).get("data") or []) + (old.get("stock_news", {}).get("data") or [])
    rows, diagnostics = [], []
    for source in settings["feeds"]:
        try:
            parsed = parse_feed(client.get(source["url"]), source, cutoff)
            rows.extend({**r, "feed_id": source["id"], "collected_at": now(), "stale": False} for r in parsed)
            diagnostics.append({"name": source["publisher"], "url": source["url"], "status": "ok", "count": len(parsed), "collected_at": now()})
        except Exception:
            retained = {r["url"]: r for r in old_rows if r.get("feed_id") == source["id"] and r.get("published_at", "") >= cutoff.isoformat()}
            rows.extend({**r, "stale": True} for r in retained.values())
            diagnostics.append({"name": source["publisher"], "url": source["url"], "status": "stale" if retained else "error", "error": "공식 피드 접근 실패"})
    rows = sorted({r["url"]: r for r in rows}.values(), key=lambda r: r["published_at"], reverse=True)
    macro = [r for r in rows if not r.get("symbol")]
    companies = [r for r in rows if r.get("symbol")]
    market = macro + [r for r in companies if r["impact_tag"] in ("실적", "AI·반도체", "관세", "에너지")]
    return sorted(market, key=lambda r:r["published_at"], reverse=True)[:60], companies[:100], diagnostics


def parse_house_index(raw, year):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        filename = next(n for n in z.namelist() if n.lower() == f"{year}fd.txt")
        if z.getinfo(filename).file_size > 10 * 1024 * 1024:
            raise ValueError("House index too large")
        rows = csv.DictReader(io.StringIO(z.read(filename).decode("utf-8-sig")), delimiter="\t")
        out = []
        for r in rows:
            filed = iso_date(r.get("FilingDate"))
            docid = r.get("DocID", "")
            if r.get("FilingType") == "P" and filed and docid.isdigit():
                out.append({"firstName": r["First"], "lastName": r["Last"], "disclosureDate": filed,
                            "document_id": docid, "chamber": "house", "state_district": r.get("StateDst"),
                            "link": f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{docid}.pdf"})
        return sorted(out, key=lambda r:(r["disclosureDate"],r["document_id"]), reverse=True)


def parse_transaction_cells(cells, document, page_number, row_number):
    if len(cells) != 8:
        return None
    clean = [text((c or "").replace("\x00", "")) for c in cells]
    date_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", clean[4])
    transaction_date = iso_date(date_match.group()) if date_match else None
    transaction_type = re.match(r"^(P|S|E)(?:\s*\((partial|full)\))?(?:\s|$)", clean[3])
    amount = re.search(r"\$[\d,]+\s*-\s*\$[\d,]+|Over\s+\$[\d,]+", clean[6], re.I)
    if not transaction_date or not transaction_type or not amount or not clean[2]:
        return None
    if transaction_date > document["disclosureDate"]:
        return None
    asset = re.split(r"\bFiling Status\b|\bSubholding\b|F\s*S\s*:", clean[2], maxsplit=1)[0].strip()
    ticker = re.search(r"\(([A-Z][A-Z0-9.\-]{0,14})\)\s*\[", asset)
    return {**document, "assetDescription": asset[:300], "symbol": ticker.group(1) if ticker else None,
            "transactionDate": transaction_date, "type": {"P":"매수", "S":"매도", "E":"교환"}[transaction_type.group(1)] + (" (일부)" if transaction_type.group(2) == "partial" else ""),
            "owner": clean[1] or "미표기", "amount": amount.group(), "page": page_number,
            "row_id": f"{document['document_id']}:{page_number}:{row_number}", "source_type": "official_house_pdf"}


def parse_house_pdf(raw, document, max_pages=8):
    import pdfplumber
    trades, rejected = [], 0
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        first = pdf.pages[0].extract_text() or ""
        # The index includes candidates/former members: do not label those as members.
        if not re.search(r"Status:\s*Member\b", first):
            return [], {**document, "status": "not_current_member", "parsed_rows": 0}
        if len(pdf.pages) > max_pages:
            return [], {**document, "status": "too_many_pages", "parsed_rows": 0}
        for page_number, page in enumerate(pdf.pages, 1):
            for table in page.find_tables():
                if not table.rows:
                    continue
                header = table.extract()[0]
                if len(header) != 8 or "Asset" not in text(header[2]) or "Amount" not in text(header[6]):
                    continue
                bounds = table.rows[0].cells
                if any(b is None for b in bounds):
                    continue
                # Use header column geometry even where the PDF merges a whole body row.
                for row_number, row in enumerate(table.rows[1:], 1):
                    cells = [page.crop((b[0], row.bbox[1], b[2], row.bbox[3])).extract_text() or "" for b in bounds]
                    parsed = parse_transaction_cells(cells, document, page_number, row_number)
                    if parsed:
                        trades.append(parsed)
                    elif re.search(r"\d{2}/\d{2}/\d{4}", " ".join(cells)):
                        rejected += 1
    return trades, {**document, "status": "partial" if rejected else "parsed" if trades else "unparsed", "parsed_rows": len(trades), "rejected_rows": rejected}


def collect_house(client, settings):
    today = datetime.now(KST).date()
    documents = []
    years = [today.year] + ([today.year - 1] if today.month == 1 else [])
    for year in years:
        documents.extend(parse_house_index(client.get(f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"), year))
    documents = [d for d in documents if d["disclosureDate"] <= today.isoformat()]
    documents.sort(key=lambda d:(d["disclosureDate"],d["document_id"]), reverse=True)
    selected = documents[:settings.get("house_pdf_limit", 20)]
    trades, reports = [], []
    cache_dir = ROOT / "work/ptr-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for document in selected:
        cache = cache_dir / (document["document_id"] + ".json")
        try:
            # Access to original filings still uses the public official endpoint.
            cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
            if cached.get("parser_version") == 2 and cached.get("checked_at", "") >= (datetime.now(timezone.utc) - timedelta(days=1)).isoformat():
                parsed, report = cached["trades"], cached["report"]
            else:
                time.sleep(0.15)
                parsed, report = parse_house_pdf(client.get(document["link"]), document, settings.get("house_max_pages", 8))
                report["checked_at"] = now()
                cache.write_text(json.dumps({"trades": parsed, "report": report, "parser_version":2, "checked_at":now()}, ensure_ascii=False), encoding="utf-8")
            trades.extend(parsed); reports.append(report)
        except Exception:
            reports.append({**document, "status": "error", "parsed_rows": 0})
    metadata = {"source": "U.S. House Clerk official PTR", "index_documents": len(documents), "selected_documents": len(selected),
                "documents": reports, "senate_status": "manual_only", "coverage": "최근 하원 공시 일부 · 상원 미수집", "collected_at": now()}
    return trades, metadata


def yahoo_universe(yf, country, target):
    from yfinance import EquityQuery
    exchanges = {"US": ["NMS", "NYQ", "NGM", "NCM", "ASE"], "KR": ["KSC", "KOE"]}[country]
    query = EquityQuery("and", [EquityQuery("eq", ["region", country.lower()]), EquityQuery("is-in", ["exchange", *exchanges]), EquityQuery("gt", ["intradaymarketcap", 0])])
    quotes = []
    # Overfetch for duplicate share classes. All results are already sorted by cap.
    for offset in range(0, target + 250, 250):
        response = yf.screen(query, size=250, offset=offset, sortField="intradaymarketcap", sortAsc=False)
        page = response.get("quotes", []) if isinstance(response, dict) else []
        if not page:
            break
        quotes.extend(page)
        if len(page) < 250:
            break
    return rank_quotes(quotes, country, target)


def rank_quotes(quotes, country, target):
    currency = "KRW" if country == "KR" else "USD"
    output, seen = [], set()
    for q in sorted(quotes, key=lambda q:q.get("marketCap") or 0, reverse=True):
        symbol = q.get("symbol", "")
        name = q.get("longName") or q.get("shortName") or symbol
        if q.get("quoteType") != "EQUITY" or q.get("currency") != currency or not q.get("marketCap"):
            continue
        if country == "KR" and (not symbol.endswith((".KS", ".KQ")) or not re.match(r"^\d{5}0\.", symbol)):
            continue  # Korean preferred-share codes do not end in 0.
        identity = re.sub(r"\s+Class\s+[A-Z](?:\s+.*)?$", "", name, flags=re.I).casefold()
        if identity in seen:
            continue
        seen.add(identity)
        output.append({"symbol": symbol, "name": name, "market_cap": q["marketCap"], "currency": currency,
                       "rank": len(output) + 1, "quote": q})
        if len(output) == target:
            break
    return output


def quote_earnings(q, start, end):
    a, b = q.get("earningsTimestampStart") or q.get("earningsTimestamp"), q.get("earningsTimestampEnd") or q.get("earningsTimestamp")
    if not a or not b:
        return None
    from zoneinfo import ZoneInfo
    try:
        zone = ZoneInfo(q.get("exchangeTimezoneName") or ("Asia/Seoul" if q["symbol"].endswith((".KS", ".KQ")) else "America/New_York"))
        first = datetime.fromtimestamp(a, zone).date().isoformat()
        last = datetime.fromtimestamp(b, zone).date().isoformat()
    except (ValueError, KeyError, OSError):
        return None
    if first != last or not start <= first <= end:
        return None  # Never pick one endpoint of a provider-estimated date range.
    return {"symbol": q["symbol"], "date": first, "eps_estimated": q.get("epsEstimate"), "status": "provider_schedule_unconfirmed",
            "provider_estimated": q.get("isEarningsDateEstimate"), "source_url": "https://finance.yahoo.com/quote/" + q["symbol"] + "/calendar/",
            "source": "Yahoo Finance (unofficial)", "checked_at": now()}


def free_calendar(client, settings, previous):
    import yfinance as yf
    today = datetime.now(KST).date()
    start, end = today.isoformat(), (today + timedelta(days=90)).isoformat()
    output = {"from": start, "to": end, "ranked_at": now(), "source": "Yahoo Finance screener (unofficial)", "countries": {}}
    old_countries = ((previous or {}).get("sections", {}).get("calendar", {}).get("data") or {}).get("countries", {})
    for country, target in (("KR", 100), ("US", 300)):
        try:
            ranked = yahoo_universe(yf, country, target)
            if not ranked:
                raise ValueError("No ranked companies")
            events = [event for row in ranked if (event := quote_earnings(row["quote"], start, end))]
            universe = [{k:v for k,v in row.items() if k != "quote"} for row in ranked]
            symbols = {row["symbol"] for row in universe}
            for official in settings.get("official_earnings", []):
                if official["country"] != country or official["symbol"] not in symbols or not start <= official["date"] <= end:
                    continue
                try:
                    page = text(client.get(official["source_url"]).decode("utf-8", errors="replace"))
                    if official["date_evidence"].casefold() not in page.casefold() or official["announcement_evidence"].casefold() not in page.casefold():
                        continue
                    events = [e for e in events if e["symbol"] != official["symbol"]]
                    events.append({"symbol": official["symbol"], "date": official["date"], "status": "official_confirmed",
                                   "source_url": official["source_url"], "source": "Company official announcement", "checked_at": now()})
                except Exception:
                    pass
            output["countries"][country] = {"target": target, "covered": len(universe), "coverage_complete": False,
                "target_reached": len(universe) == target, "rank_scope": "무료 제공처가 수록한 현지 종목·회사명 기준 중복 제외 / 공식 거래소 순위 아님",
                "universe": universe, "events": sorted(events, key=lambda e:(e["date"],e["symbol"])),
                "missing_schedule": sorted(symbols - {e["symbol"] for e in events}), "status": "ok", "collected_at": now()}
        except Exception:
            old = old_countries.get(country)
            output["countries"][country] = {**(old or {"target":target,"covered":0,"universe":[],"events":[],"missing_schedule":[],"coverage_complete":False}), "status": "stale" if old else "error", "error": "무료 시총·예정일 제공처 접근 실패"}
    return output


def collect_free(client, config, previous=None):
    settings = json.loads((ROOT / "config/free_sources.json").read_text(encoding="utf-8"))
    result = {"attempted_at": now(), "mode": "free", "sections": {}, "sources": []}
    def section(name, fn):
        try:
            data, meta = fn()
            result["sections"][name] = {"status": "ok", "updated_at": now(), "data": data, "meta": meta}
        except Exception:
            old = (previous or {}).get("sections", {}).get(name, {})
            result["sections"][name] = {"status": "stale" if old.get("data") is not None else "error", "updated_at": old.get("updated_at"), "data": old.get("data"), "meta": old.get("meta"), "error": "무료 원문 수집 실패 · 원문 접근 상태 확인 필요"}
    def managers():
        values = []
        old = {m["cik"]:m for m in (previous or {}).get("sections",{}).get("institutions",{}).get("data") or []}
        for m in config["institutions"]:
            try:
                values.append({"status":"ok", "collected_at":now(), **institution(client,m,config["cusips"])})
            except Exception as exc:
                retained = old.get(m["cik"], {})
                values.append({**retained, **m,"status":"stale" if retained.get("holdings") else "error","error":str(exc) if isinstance(exc,ValueError) else "SEC 접근 실패 · 접근 제한 또는 제공처 오류"})
        return values, {"source":"SEC EDGAR original XML","contact":"Repository issues URL; SEC_USER_AGENT may override"}
    section("institutions", managers)
    try:
        market, companies, diagnostics = collect_feeds(client, settings, previous)
        result["sources"].extend(diagnostics)
        for name, rows in (("market_news",market),("stock_news",companies)):
            relevant = [d for d in diagnostics if name == "market_news" or d["name"] in {s["publisher"] for s in settings["feeds"] if s.get("symbol")}]
            successes = any(d["status"] == "ok" for d in relevant)
            result["sections"][name] = {"status":"ok" if successes else "stale" if rows else "error", "updated_at":now() if successes else (previous or {}).get("sections",{}).get(name,{}).get("updated_at"), "data":rows,"meta":{"window_days":30,"summary":"공식 피드 핵심 발췌 · 생성형 요약 아님"}}
    except Exception:
        section("market_news", lambda: (_ for _ in ()).throw(ValueError()))
        section("stock_news", lambda: (_ for _ in ()).throw(ValueError()))
    section("ptr", lambda: collect_house(client,settings))
    section("calendar", lambda: (free_calendar(client,settings,previous), {"source":"Yahoo Finance unofficial / official company announcements override"}))
    return result
