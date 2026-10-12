const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs'), path = require('path'), http = require('http'), assert = require('assert/strict');
const holding = (cusip, symbol, issuer) => ({cusip,symbol,issuer,shares:10,weight_pct:25,change:'new',share_change:10});
const manager = (cik, holdings) => ({cik,holdings,name:'Fixture '+cik,status:'ok',period:'2026-06-30',previous_period:'2026-03-31',filed_at:'2026-08-14',source_url:'https://www.sec.gov/',previous_source_url:'https://www.sec.gov/'});
const ok = data => ({status:'ok',data});
let fixture = {sections:{institutions:ok([manager('1',[holding('X','AAPL','Apple First')]),manager('2',[holding('Y','OTHER','Apple Second')])]),
  stock_news:ok([{symbol:'AAPL',title:'Fixture Apple news',url:'https://example.com',publisher:'Fixture'}]),
  market_news:ok([{title:'Fixture Fed news',impact_tag:'금리',publisher:'Source A',url:'https://example.com/a'}, {title:'Fixture earnings',impact_tag:'실적',publisher:'Source B',url:'https://example.com/b'}]),
  ptr:ok([{firstName:'Alpha',lastName:'Tester',chamber:'house',symbol:'AAPL'}, {firstName:'Beta',lastName:'Tester',chamber:'senate',symbol:'MSFT'}]),
  calendar:ok({from:'2026-10-12',to:'2027-01-10',ranked_at:'2026-10-12T00:00:00Z',countries:{KR:{covered:1,target:100,coverage_complete:false,missing_schedule:[],universe:[{symbol:'TEST',name:'검증 회사',rank:1}],events:[{symbol:'TEST',date:'2026-10-20'},{symbol:'TEST',date:'2026-11-20'}]}}})}};
(async()=>{
  const root=path.resolve(__dirname,'..'); process.chdir(root); fs.mkdirSync('work',{recursive:true});
  const server=http.createServer((req,res)=>{const pathname=req.url.split('?')[0], p=path.join(root,pathname==='/'?'index.html':pathname);try{res.setHeader('Content-Type',p.endsWith('.js')?'application/javascript':p.endsWith('.css')?'text/css':p.endsWith('.json')?'application/json':'text/html');res.end(fs.readFileSync(p));}catch{res.statusCode=404;res.end();}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r)); let browser;
  try {
    browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {})});
    const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true}), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:'+server.address().port);
    await page.waitForSelector('#markets .card');
    await page.waitForFunction(()=>document.querySelector('#calendar-data').textContent.trim().length>0);
    await page.locator('#markets .favorite').first().click();
    await page.check('#favorites-only'); assert.equal(await page.locator('#markets .card').count(),1);
    await page.reload(); await page.waitForSelector('#markets .favorite[aria-pressed="true"]');
    await page.fill('#symbol','MSFT'); await page.locator('#search button').click();
    await page.reload(); await page.waitForSelector('#recent-searches button');
    assert.ok((await page.locator('#recent-searches').innerText()).includes('MSFT'));
    await page.screenshot({path:'work/desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:'work/mobile.png',fullPage:true});
    await page.route('**/data/research.json?*',route=>route.fulfill({json:fixture}));
    await page.reload(); await page.waitForSelector('#institutions .card');
    await page.fill('#symbol','Apple'); await page.locator('#search button').click();
    assert.equal(await page.locator('#security-choice').isVisible(),true);
    assert.equal(await page.locator('#search-results table').count(),0);
    await page.selectOption('#security','X');
    assert.ok((await page.locator('#search-results').innerText()).includes('50%'));
    assert.ok((await page.locator('#stock-news').innerText()).includes('Fixture Apple news'));
    await page.selectOption('#news-topic','금리'); assert.equal(await page.locator('#market-news .card').count(),1);
    await page.fill('#news-query','Source B'); assert.equal(await page.locator('#market-news .card').count(),0);
    await page.selectOption('#ptr-chamber','house');
    assert.ok((await page.locator('#ptr-data').innerText()).includes('Alpha'));
    assert.ok(!(await page.locator('#ptr-data').innerText()).includes('Beta'));
    await page.fill('#calendar-from','2026-10-20'); await page.fill('#calendar-to','2026-10-20'); await page.locator('#calendar-to').blur();
    assert.equal(await page.locator('#calendar-data > .table-wrap tbody tr').count(),1);
    const csvWait=page.waitForEvent('download'); await page.click('#calendar-csv'); const csv=await csvWait;
    await csv.saveAs('work/test-calendar.csv'); const csvText=fs.readFileSync('work/test-calendar.csv','utf8');
    assert.ok(csvText.includes('2026-10-20')); assert.ok(!csvText.includes('2026-11-20'));
    const icsWait=page.waitForEvent('download'); await page.click('#calendar-ics'); const ics=await icsWait;
    await ics.saveAs('work/test-calendar.ics'); assert.ok(fs.readFileSync('work/test-calendar.ics','utf8').includes('STATUS:TENTATIVE'));
    await page.fill('#calendar-from','2026-11-01'); await page.locator('#calendar-from').blur();
    assert.equal(await page.locator('#calendar-ics').isDisabled(),true);
    await page.click('#calendar-reset'); assert.equal(await page.locator('#calendar-data > .table-wrap tbody tr').count(),2);
    await page.selectOption('#country','US'); assert.ok((await page.locator('#calendar-data').innerText()).includes('이 시장의 일정 데이터가 없습니다'));
    fixture.sections.institutions={status:'not_configured',data:null}; await page.reload();
    await page.waitForSelector('#stock-news .card'); await page.fill('#symbol','AAPL'); await page.locator('#search button').click();
    assert.ok((await page.locator('#stock-news').innerText()).includes('Fixture Apple news'));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    console.log('PASS: desktop/mobile, persistence, ambiguous search, independent news, filters, CSV/ICS downloads, invalid dates, missing country, no browser errors');
  } finally {if(browser)await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
