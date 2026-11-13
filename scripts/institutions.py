"""Public SEC 13F holdings. No credentials, estimated positions, or synthetic values."""
import json, os, time, re
from pathlib import Path
from datetime import datetime, timezone
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
UA = 'StockMarketDashboard/1.0 contact kws4323@gmail.com'
CATALOG = [
 ('nbim','NBIM','국부펀드',1374170,'Norges Bank의 미국 13F 공개분'),
 ('temasek','Temasek','국부펀드',1021944,'Temasek Holdings의 미국 13F 공개분'),
 ('gic','GIC','국부펀드',None,'연례 자산배분 공개. 개별 투자 상세는 비공개'),
 ('mubadala','Mubadala','국부펀드',1704268,'Mubadala Investment Co PJSC의 미국 13F 공개분'),
 ('pif','PIF','국부펀드',1767640,'Public Investment Fund의 미국 13F 공개분'),
 ('qia','QIA','국부펀드',None,'공개 투자 사례와 전체 보유목록은 다릅니다. 정량 비교 미연결'),
 ('kic','KIC','국부펀드',1441689,'Korea Investment Corp의 미국 13F 공개분'),
 ('nps','국민연금','연기금',1608046,'국민연금의 미국 13F 공개분. 국내 주식은 포함하지 않음'),
 ('gpif','GPIF','연기금',None,'종목별 보유자료는 연간 Excel 공개. 자동 정량 비교 미연결'),
 ('calpers','CalPERS','연기금',919079,'미국 13F 공개분'),
 ('calstrs','CalSTRS','연기금',1081019,'미국 13F 공개분'),
 ('cpp','CPP Investments','연기금',1283718,'Canada Pension Plan Investment Board의 미국 13F 공개분'),
 ('apg','ABP / APG','연기금',1434819,'APG Asset Management N.V. 공개분. ABP 단독 자산이 아니며 APG US 별도 법인 제외'),
 ('blackrock','BlackRock','운용사·헤지펀드',2012383,'BlackRock Inc. 및 포함 운용사 미국 13F 공개분'),
 ('jpm','JPMorgan AM','운용사·헤지펀드',19617,'대체 비교자료: JPMorgan Chase & Co 통합 13F. AM 단독 자료가 아님'),
 ('berkshire','Berkshire Hathaway','운용사·헤지펀드',1067983,'미국 13F 공개분. 비상장 자회사·현금 제외'),
 ('bridgewater','Bridgewater','운용사·헤지펀드',1350694,'미국 13F 공개분'),
 ('ark','ARK Invest','운용사·헤지펀드',1697748,'ARK Investment Management 분기 13F. 개별 ETF 일별 자료와 다름'),
 ('pershing','Pershing Square','운용사·헤지펀드',2026053,'Pershing Square Inc. 통합 분기 13F'),
 ('renaissance','Renaissance Technologies','운용사·헤지펀드',1037389,'미국 13F 공개분. Medallion 펀드 전체 포트폴리오가 아님'),
]
LINKS = {'gic':'https://www.gic.com.sg/our-portfolio/gic-reports/', 'qia':'https://www.qia.qa/', 'gpif':'https://www.gpif.go.jp/en/performance/last-years-results.html'}

def get(url):
    time.sleep(.25) # below SEC fair-access request limit
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':UA}), timeout=35) as r:
        return r.read()

def tag(root, name):
    return next((n.text or '' for n in root.iter() if n.tag.split('}')[-1] == name), '').strip()

def parse_table(raw, filed):
    root = ET.fromstring(raw)
    rows, all_value = [], 0
    factor = 1000 if filed < '2023-01-03' else 1
    for n in root.iter():
        if n.tag.split('}')[-1] != 'infoTable': continue
        value = int(tag(n,'value')) * factor
        all_value += value
        if tag(n,'putCall') or tag(n,'sshPrnamtType') != 'SH': continue
        code = tag(n,'cusip').upper()
        if not code or value < 0: raise ValueError('invalid holding')
        rows.append({'id':code, 'name':tag(n,'nameOfIssuer'), 'class':tag(n,'titleOfClass'), 'usd':value, 'shares':float(tag(n,'sshPrnamt'))})
    return rows, all_value

def merge(rows):
    out = {}
    for row in rows:
        key = row['id']
        if key not in out: out[key] = dict(row)
        else:
            out[key]['usd'] += row['usd']
            out[key]['shares'] += row['shares']
    return sorted(out.values(), key=lambda r:-r['usd'])

def filing(cik, f):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['accessionNumber'].replace('-','')}/"
    # Complete submission contains the authoritative XML documents and avoids guessing filenames.
    raw = get(base + f['accessionNumber'] + '.txt').decode('utf-8')
    docs = re.findall(r'<XML>\s*(.*?)\s*</XML>', raw, re.S | re.I)
    primary, tables = None, []
    for doc in docs:
        root = ET.fromstring(doc)
        if root.tag.split('}')[-1] == 'edgarSubmission': primary = root
        elif root.tag.split('}')[-1] == 'informationTable': tables.append(doc)
    if primary is None or not tables: raise ValueError('missing SEC XML')
    rows, value = [], 0
    for doc in tables:
        r, v = parse_table(doc, f['filingDate']); rows.extend(r); value += v
    factor = 1000 if f['filingDate'] < '2023-01-03' else 1
    if value != int(tag(primary,'tableValueTotal')) * factor: raise ValueError('SEC total mismatch')
    return rows, tag(primary,'amendmentType'), base + f['accessionNumber'] + '-index.html'

def collect(cik, old):
    sub = json.loads(get(f'https://data.sec.gov/submissions/CIK{cik:010d}.json'))
    recent = sub['filings']['recent']
    files = [dict(zip(recent, vs)) for vs in zip(*recent.values())]
    files = [f for f in files if f['form'] in ('13F-HR','13F-HR/A') and f['reportDate'] and f['filingDate'] <= datetime.now(timezone.utc).date().isoformat()]
    periods = sorted({f['reportDate'] for f in files if f['form']=='13F-HR'}, reverse=True)[:2]
    if not periods: raise ValueError('no recent holdings reports')
    reports = []
    for period in periods:
        fs = sorted([f for f in files if f['reportDate']==period], key=lambda f:(f['filingDate'],f['accessionNumber']))
        signature = '|'.join(f['accessionNumber'] for f in fs)
        saved = next((r for r in old if r.get('signature')==signature), None)
        if saved: reports.append(saved); continue
        rows, sources, initialized = [], [], False
        for f in fs:
            new, amendment, url = filing(cik,f)
            if f['form']=='13F-HR' or amendment.upper()=='RESTATEMENT': rows = new; initialized = True
            elif amendment.upper()=='NEW HOLDINGS' and initialized: rows.extend(new)
            else: raise ValueError('unsupported amendment')
            sources.append({'url':url,'filed':f['filingDate'],'form':f['form']})
        rows = merge(rows)
        reports.append({'period':period,'filed':fs[-1]['filingDate'],'signature':signature,'sources':sources,'holdings':rows,'totalUsd':sum(r['usd'] for r in rows)})
    return reports

def main():
    path = ROOT/'data/institutions.json'
    old = json.loads(path.read_text('utf-8')) if path.exists() else {'institutions':[]}
    today = datetime.now(timezone.utc).date().isoformat()
    items = []
    for id, name, group, cik, scope in CATALOG:
        prior = next((x for x in old['institutions'] if x['id']==id), {})
        item = {'id':id,'name':name,'group':group,'cik':cik,'scope':scope,'frequency':'분기' if cik else '연간·수시','url':f'https://www.sec.gov/edgar/browse/?CIK={cik}' if cik else LINKS[id], 'reports':prior.get('reports',[]), 'status':'unconnected'}
        if cik:
            if prior.get('checked')==today:
                item.update({k:prior[k] for k in ('checked','status','error') if k in prior})
            else:
                try:
                    item['reports'] = collect(cik,item['reports']); item['status']='ok'
                except Exception as e:
                    item['status']='stale' if item['reports'] else 'error'; item['error']=type(e).__name__
                    print(name, type(e).__name__, str(e)[:160], flush=True)
                item['checked']=today
        items.append(item)
        print(name, item['status'], len(item['reports']), flush=True)
    result = {'schemaVersion':1,'institutions':items}
    path.parent.mkdir(exist_ok=True); path.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    public = ROOT/'site/data/institutions.json'; public.parent.mkdir(exist_ok=True)
    public.write_text(path.read_text('utf-8'),encoding='utf-8')

if __name__=='__main__': main()
