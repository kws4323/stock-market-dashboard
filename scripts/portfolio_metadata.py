"""Conservative issuer mapping; unclassified holdings remain explicitly unknown."""
import json, re
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf
ROOT=Path(__file__).resolve().parents[1]
# Exact SEC issuer aliases, with share class checks where issuers have multiple listings.
ALIASES={
'AAPL':['APPLE INC'],'MSFT':['MICROSOFT CORP'],'NVDA':['NVIDIA CORP','NVIDIA CORPORATION'],
'AMZN':['AMAZON COM INC'],'META':['META PLATFORMS INC'],'TSLA':['TESLA INC'],
'GOOGL':['ALPHABET INC'],'AVGO':['BROADCOM INC'],'AMD':['ADVANCED MICRO DEVICES INC'],
'JPM':['JPMORGAN CHASE & CO'],'V':['VISA INC'],'MA':['MASTERCARD INCORPORATED'],
'KO':['COCA COLA CO'],'AXP':['AMERICAN EXPRESS CO'],'BAC':['BANK OF AMER CORP'],
'CVX':['CHEVRON CORP','CHEVRON CORPORATION'],'OXY':['OCCIDENTAL PETE CORP'],
'BRK-B':['BERKSHIRE HATHAWAY INC DEL'],'UNH':['UNITEDHEALTH GROUP INC'],
'LLY':['ELI LILLY & CO','LILLY ELI & CO'],'WMT':['WALMART INC'],'COST':['COSTCO WHSL CORP NEW'],
'XOM':['EXXON MOBIL CORP'],'JNJ':['JOHNSON & JOHNSON'],'PG':['PROCTER & GAMBLE CO'],
'HD':['HOME DEPOT INC'],'NFLX':['NETFLIX INC'],'PLTR':['PALANTIR TECHNOLOGIES INC'],
'ORCL':['ORACLE CORP'],'CRM':['SALESFORCE INC'],'ABBV':['ABBVIE INC'],
'ISRG':['INTUITIVE SURGICAL INC'],'ADBE':['ADOBE INC'],'PEP':['PEPSICO INC'],
'SPY':['SPDR S&P 500 ETF TR'],'QQQ':['INVESCO QQQ TR'],'VOO':['VANGUARD INDEX FDS'],'IVV':['ISHARES TR']}
def norm(s):return re.sub(r'[^A-Z0-9]','',s.upper())
def match(h):
    for symbol,aliases in ALIASES.items():
        if norm(h['name']) not in [norm(a) for a in aliases]:continue
        cls=norm(h.get('class',''))
        if symbol=='GOOGL':
            if cls in ('CAPSTKCLA','CLA'):return 'GOOGL'
            if cls in ('CAPSTKCLC','CLC'):return 'GOOG'
            continue
        if symbol=='BRK-B' and cls not in ('CLBNEW','CLB'):continue
        if symbol=='VOO' and cls not in ('S&P500ETF','SP500ETF'):continue
        if symbol=='IVV' and cls not in ('CORESP500ETF',):continue
        if any(x in cls for x in ('PUT','CALL','PFD','WEXP','WTS','WARR','NOTE','DEB')):continue
        return symbol
    return None
def main():
    data=json.loads((ROOT/'data/institutions.json').read_text('utf-8'))
    dest=ROOT/'data/portfolio-metadata.json'
    previous=json.loads(dest.read_text('utf-8')) if dest.exists() else {}
    today=datetime.now(timezone.utc).date().isoformat(); symbols=previous.get('symbols',{});mapping={}
    for i in data['institutions']:
        for r in i['reports']:
            for h in r['holdings']:
                symbol=match(h)
                if symbol:mapping[h['id']]=symbol
    for symbol in sorted(set(mapping.values())):
        if symbols.get(symbol,{}).get('checked')==today:continue
        item={'symbol':symbol,'checked':today,'sector':None,'splits':[],'splitStatus':'unknown'}
        try:
            t=yf.Ticker(symbol);info=t.get_info()
            item['sector']='ETF / 펀드' if info.get('quoteType')=='ETF' else info.get('sector')
            item['source']='https://finance.yahoo.com/quote/'+symbol+'/profile/'
            history=t.history(period='5y',auto_adjust=False,actions=True,raise_errors=True)
            if not history.empty and 'Stock Splits' in history:
                item['splits']=[{'date':d.date().isoformat(),'ratio':float(v)} for d,v in history['Stock Splits'].items() if v>0]
                item['splitStatus']='ok';item['splitStart']=history.index[0].date().isoformat()
        except Exception as e:print('Metadata',symbol,type(e).__name__,flush=True)
        symbols[symbol]=item
    result={'checked':today,'mapping':mapping,'symbols':symbols}
    for path in [dest,ROOT/'site/data/portfolio-metadata.json']:
        path.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Metadata mapped securities',len(mapping),'sectors',sum(bool(x.get('sector')) for x in symbols.values()),flush=True)
if __name__=='__main__':main()
