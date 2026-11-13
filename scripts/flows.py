"""KRX cash equities only. No estimates; history survives Actions runs in Git."""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {"foreign": "외국인", "institution": "기관합계", "individual": "개인"}
KST = ZoneInfo("Asia/Seoul")

def top_sellers(rows):
    return sorted((r for r in rows if r["net"] < 0), key=lambda r: (r["net"], r["code"]))[:5]

def streak(history, sessions, day, market, group, code):
    count = 0
    for date in reversed([s for s in sessions if s <= day]):
        entry = history.get(date)
        if entry is None:
            return {"days": count, "atLeast": True}
        if not any(r["code"] == code for r in entry["markets"][market][group]["topSell"]):
            return {"days": count, "atLeast": False}
        count += 1
    return {"days": count, "atLeast": True}

def collect_day(stock, day):
    compact = day.replace("-", "")
    markets = {}
    for market in ("KOSPI", "KOSDAQ"):
        totals = stock.get_market_trading_value_by_investor(compact, compact, market)
        if totals.empty or not {"매수", "매도", "순매수"}.issubset(totals.columns):
            raise ValueError("KRX totals unavailable")
        markets[market] = {}
        for key, label in GROUPS.items():
            time.sleep(1)
            frame = stock.get_market_net_purchases_of_equities(compact, compact, market, label)
            if frame.empty or not {"종목명", "매수거래대금", "매도거래대금", "순매수거래대금"}.issubset(frame.columns):
                raise ValueError("KRX rankings unavailable")
            total = totals.loc[label]
            buy, sell, net = (int(total[c]) for c in ("매수", "매도", "순매수"))
            if buy - sell != net or buy + sell <= 0:
                raise ValueError("KRX totals failed validation")
            rows = []
            for code, row in frame.iterrows():
                r = {"code": str(code), "name": str(row["종목명"]), "market": market,
                     "net": int(row["순매수거래대금"])}
                if int(row["매수거래대금"]) - int(row["매도거래대금"]) != r["net"]:
                    raise ValueError("KRX row failed validation")
                rows.append(r)
            markets[market][key] = {"buy": buy, "sell": sell, "net": net, "topSell": top_sellers(rows)}
    markets["ALL"] = {}
    for group in GROUPS:
        a, b = markets["KOSPI"][group], markets["KOSDAQ"][group]
        markets["ALL"][group] = {field: a[field] + b[field] for field in ("buy", "sell", "net")}
        markets["ALL"][group]["topSell"] = top_sellers(a["topSell"] + b["topSell"])
    return markets

def main():
    now = datetime.now(KST)
    path = ROOT / "data" / "flows.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schemaVersion": 1, "history": {}}
    if saved.get("schemaVersion") != 1 or not isinstance(saved.get("history"), dict):
        raise ValueError("Invalid history; refusing to overwrite")
    history = saved["history"]
    status, message = "auth_required", "KRX 데이터 연결 대기: 저장소의 Actions secrets에 KRX_ID와 KRX_PW를 등록해 주세요."
    sessions = saved.get("sessions", [])
    if os.environ.get("KRX_ID") and os.environ.get("KRX_PW"):
        try:
            import exchange_calendars as xcals
            from pykrx import stock
            start = min(history) if history else (now - timedelta(days=120)).date().isoformat()
            calendar = xcals.get_calendar("XKRX", start=start, end=now.date().isoformat())
            eligible = [s for s in calendar.sessions if calendar.session_close(s).to_pydatetime() + timedelta(minutes=15) <= now]
            sessions = [s.strftime("%Y-%m-%d") for s in eligible]
            if not sessions:
                raise ValueError("No closed trading session")
            latest = sessions[-1]
            candidates = [s for s in sessions[-10:] if s not in history]
            if latest in history and not history[latest].get("eveningUpdate"):
                candidates.append(latest)
            # Latest session first, then fill gaps on subsequent runs. Never bridge a missing session.
            for day in sorted(set(candidates), reverse=True)[:5]:
                markets = collect_day(stock, day)
                history[day] = {"markets": markets, "collectedAt": now.isoformat(),
                                "eveningUpdate": day < now.date().isoformat() or (now.hour, now.minute) >= (20, 15)}
                print("Collected KRX session", day, flush=True)
            status, message = "ok", "장 마감 후 집계 · 20:15 이후 시간외 포함 자료 재조회 · 제공처 지연/수정 가능"
        except Exception as exc:
            status, message = "error", "KRX 수집 실패. 기존 자료는 보존했습니다. 계정 설정과 제공처 상태를 확인해 주세요."
            print("KRX collection error:", type(exc).__name__, flush=True)
    saved.update({"sessions": sessions, "history": history})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    public = {**saved, "status": status, "message": message, "checkedAt": now.isoformat(),
              "source": "KRX via pykrx", "latestDate": max(history) if history else None,
              "expectedDate": sessions[-1] if sessions else None}
    # Derived streaks live only in the published view, not the canonical history.
    public = json.loads(json.dumps(public))
    for day, entry in public["history"].items():
        for market, groups in entry["markets"].items():
            for group, data in groups.items():
                for row in data["topSell"]:
                    row["streak"] = streak(history, sessions, day, market, group, row["code"])
    target = ROOT / "site" / "data" / "flows.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(public, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("KRX status:", status, "; stored sessions:", len(history))

if __name__ == "__main__":
    main()
