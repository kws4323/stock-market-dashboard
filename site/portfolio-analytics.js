(() => {
 const $=id=>document.getElementById(id),M=window.PortfolioMath;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=v=>v.toLocaleString('ko-KR',{maximumFractionDigits:2});
 const signed=v=>(v>0?'+':'')+num(v);
 let state=null,meta={},tracked=[];
 try{tracked=JSON.parse(localStorage.getItem('portfolio-tracked')||'[]');if(!Array.isArray(tracked))tracked=[]}catch{}
 const section=$('portfolio-analytics');
 const table=(head,body)=>`<div class="inst-table-wrap"><table class="inst-table"><thead><tr>${head.map(x=>'<th>'+x+'</th>').join('')}</tr></thead><tbody>${body||'<tr><td colspan="'+head.length+'">표시할 자료가 없습니다.</td></tr>'}</tbody></table></div>`;
 section.innerHTML=`<section class="inst-box"><h2>전기 대비 포트폴리오 변화</h2><p class="inst-muted">아래 기관·기준일은 기존 조회 선택과 연동됩니다. 신규 편입·전량 매도는 공개 목록 진입·이탈을 뜻하며 실제 거래 확정이 아닙니다. 비공개 해제, 합병, 식별코드 변경의 영향이 있을 수 있습니다.</p><div class="inst-toolbar"><select id="pa-kind" aria-label="변화 유형"><option value="all">전체 변화</option><option value="new">신규 편입</option><option value="exit">전량 매도 · 목록 이탈</option><option value="increase">보유 증가</option><option value="decrease">보유 감소</option></select><input id="pa-query" type="search" placeholder="종목명·코드 검색" aria-label="변화 종목 검색"></div><p id="pa-change-note" class="inst-muted"></p><div id="pa-changes"></div></section>
 <section class="inst-box"><h2>여러 기관의 동시 신규 편입</h2><p class="inst-muted">선택한 기관 중 같은 분기의 직전 분기 대비 신규 공시 종목을 비교합니다. 식별코드 변경 의심 건은 제외합니다. 단순 공통 보유와 다릅니다.</p><p id="pa-new-note" class="inst-muted"></p><div id="pa-new"></div></section>
 <section class="inst-box"><h2>내 관심종목 × 기관 보유</h2><p class="inst-muted">시장 탭 관심종목과 연결합니다. 아래에서 종목을 ‘관심’으로 추가할 수도 있습니다. 저장은 현재 브라우저에만 적용됩니다. 국내 주식과 미국 ADR은 동일 증권으로 자동 합치지 않습니다.</p><button id="pa-watch-refresh" class="btn">관심종목 다시 확인</button><div id="pa-watch"></div></section>
 <section class="inst-box"><h2>종목별 보유 추이</h2><div class="inst-toolbar"><input id="pa-security" list="pa-options" placeholder="CUSIP / ISIN 코드" aria-label="추이 증권 식별코드"><datalist id="pa-options"></datalist><select id="pa-metric" aria-label="추이 지표"><option value="shares">공시 보유 주수</option><option value="weight">공개분 내 비중 (%)</option></select><button id="pa-trend-go" class="btn">추이 보기</button></div><p id="pa-trend-note" class="inst-muted"></p><div id="pa-chart"></div><div id="pa-history"></div></section>
 <section class="inst-box"><h2>기관별 업종 비중 비교</h2><p class="inst-muted">공시 평가액 기준 · Yahoo Finance의 현재 업종 분류를 과거 보유분에도 적용합니다. 확인된 종목만 분류하며 ETF는 별도 표시합니다. 미분류를 포함한 전체 공개분을 분모로 사용합니다.</p><div id="pa-sectors"></div></section>`;
 section.insertAdjacentHTML('afterbegin','<div class="inst-toolbar"><label>분석 기관 <select id="pa-manager" aria-label="분석 기관"></select></label></div>');
 $('pa-manager').onchange=()=>{$('inst-manager').value=$('pa-manager').value;$('inst-manager').dispatchEvent(new Event('change'))};
 const getReport=i=>state.period==='latest'?i.reports[0]:i.reports.find(r=>r.period===state.period);
 const won=h=>{const fx=state.fx,v=h?.jpy!=null?(fx?.yen?h.jpy/fx.yen:null):h?.usd;if(!fx||v==null)return '환율 미확인';return num(v*fx.rate/1e8)+'억 원'};
 const buttons=r=>`<button class="btn" data-trend="${esc(r.id)}">추이</button> <button class="btn" data-track="${esc(r.id)}">관심</button>`;
 const types={new:'신규 편입',exit:'전량 매도 · 목록 이탈',increase:'보유 증가',decrease:'보유 감소',same:'동일'};
 const sectorNames={'Technology':'기술','Financial Services':'금융','Communication Services':'통신·미디어','Consumer Cyclical':'경기소비재','Consumer Defensive':'필수소비재','Healthcare':'헬스케어','Industrials':'산업재','Energy':'에너지','Basic Materials':'소재','Utilities':'유틸리티','Real Estate':'부동산'};
 function render(){if(!state)return;
  $('pa-manager').innerHTML=state.data.map(i=>`<option value="${esc(i.id)}">${esc(i.name)}</option>`).join('');$('pa-manager').value=state.manager;
  const institution=state.data.find(i=>i.id===state.manager);if(!institution)return;
  const report=getReport(institution),result=M.compare(institution,report,meta),kind=$('pa-kind').value,q=$('pa-query').value.toLowerCase();
  const rows=result.rows.filter(r=>r.type!=='same'&&(kind==='all'||r.type===kind)&&(r.name+' '+r.id+' '+(r.symbol||'')).toLowerCase().includes(q)).sort((a,b)=>M.value(b.b||b.a)-M.value(a.b||a.a));
  $('pa-change-note').textContent=institution.name+' · '+(result.reason||result.before.period+' → '+report.period)+` · ${rows.length}건 (최대 200건 표시, 검색으로 좁힐 수 있습니다). 분할 확인이 안 된 주수는 미조정으로 표시합니다.`;
  $('pa-changes').innerHTML=table(['종목 / 유형','주수 변화','비중 변화 / 금액'],rows.slice(0,200).map(r=>`<tr><td>${esc(r.name)}<small>${types[r.type]}${r.review?' · 식별코드 변경 검토':''} · ${esc(r.id)}</small>${buttons(r)}</td><td>${num(r.a?.shares||0)} → ${num(r.b?.shares||0)}<small>${r.checked?'분할 조정 후':'미조정'} ${signed(r.delta)}주${r.factor!==1?' · 분할 배수 '+num(r.factor):''}</small></td><td>${signed(r.weightChange)}%p<small>${r.b?'현재 비교기간':'이전 비교기간'} ${won(r.b||r.a)}</small></td></tr>`).join(''));
  const selected=state.data.filter(i=>state.chosen.includes(i.id)),entries=selected.map(i=>({institution:i,result:M.compare(i,getReport(i),meta)})),shared=M.overlap(entries);
  $('pa-new-note').textContent=`비교 가능 ${entries.filter(e=>!e.result.reason).length}/${selected.length}개 기관 · ${shared.length}개 결과. 제외 기관: ${entries.filter(e=>e.result.reason).map(e=>e.institution.name).join(', ')||'없음'}`;
  $('pa-new').innerHTML=table(['신규 공시 종목','보유 기준일','기관'],shared.slice(0,200).map(r=>`<tr><td>${esc(r.name)}<small>${esc(r.id)}</small>${buttons(r)}</td><td>${r.period}</td><td>${r.owners.length}곳<small>${r.owners.map(esc).join(' · ')}</small></td></tr>`).join(''));
  renderWatch(selected);renderTrend(institution);
  $('pa-sectors').innerHTML=selected.map(i=>{const r=getReport(i);if(!r)return `<article><h3>${esc(i.name)}</h3><p>해당 기준일 자료 없음</p></article>`;const sums={};let classified=0;const total=r.totalJpy??r.totalUsd;for(const h of r.holdings){const m=meta.symbols?.[meta.mapping?.[h.id]],key=m?.sector||'미분류';sums[key]=(sums[key]||0)+M.value(h);if(key!=='미분류')classified+=M.value(h)}return `<article class="inst-box"><h3>${esc(i.name)} <small>${r.period}</small></h3><p class="inst-muted">분류 금액 비율 ${total?num(classified/total*100):0}% · 분류 확인 ${esc(meta.checked||'대기')}</p>${Object.entries(sums).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div class="pa-sector"><span>${esc(sectorNames[k]||k)}</span><meter min="0" max="100" value="${total?v/total*100:0}"></meter><b>${total?num(v/total*100):0}%</b></div>`).join('')}</article>`}).join('');
 }
 function renderWatch(selected){let watch=[];try{watch=JSON.parse(localStorage.getItem('stock-watch')||'null')||[['NVDA','엔비디아'],['MSFT','마이크로소프트'],['AAPL','애플']]}catch{}
  const requests=watch.filter(x=>Array.isArray(x)).map(([s,n])=>({name:n,symbol:s,ids:Object.keys(meta.mapping||{}).filter(id=>meta.mapping[id]===s)}));
  for(const id of tracked)requests.push({name:id,symbol:'직접 추가',ids:[id]});
  $('pa-watch').innerHTML=table(['관심종목','기관 보유','공개 평가액'],requests.map(w=>{const found=[];for(const i of selected){const r=getReport(i);if(!r)continue;for(const h of r.holdings)if(w.ids.includes(h.id))found.push({i,r,h})}return `<tr><td>${esc(w.name)}<small>${esc(w.symbol)}</small>${w.symbol==='직접 추가'?'<button class="btn" data-untrack="'+esc(w.ids[0])+'">관심 해제</button>':''}</td><td>${found.length?found.map(x=>`${esc(x.i.name)} · ${x.r.period} · ${num(x.h.shares)}주 (${num(M.weight(x.h,x.r))}%)`).join('<br>'):w.ids.length?'수집한 공개분에서 확인되지 않음':'증권 식별코드 미연결 · 미보유 판단 불가'}</td><td>${found.map(x=>won(x.h)).join('<br>')||'—'}</td></tr>`}).join(''));
 }
 function renderTrend(i){const map=new Map();for(const r of i.reports)for(const h of r.holdings)map.set(h.id,h);$('pa-options').innerHTML=[...map.values()].slice(0,300).map(h=>`<option value="${esc(h.id)}">${esc(h.name)}</option>`).join('');if(!$('pa-security').value)$('pa-security').value=[...map.values()].find(h=>meta.mapping?.[h.id]==='AAPL')?.id||map.keys().next().value||'';
  const id=$('pa-security').value.trim(),h=map.get(id),metric=$('pa-metric').value;
  const latest=i.reports[0]?.period;if(!latest){$('pa-chart').innerHTML='자료 없음';$('pa-history').innerHTML='';return}
  let periods=[latest];for(let n=1;n<8;n++)periods.unshift(M.previousPeriod(periods[0],i.id==='gpif'));
  const points=periods.map(p=>{const r=i.reports.find(r=>r.period===p),h=r?.holdings.find(h=>h.id===id);return {p,r,h,y:r?(metric==='shares'?(h?.shares||0):M.weight(h,r)):null}});
  $('pa-trend-note').textContent=`${i.name} · ${h?.name||id} · ${metric==='shares'?'공시 원주수 (분할 미조정)':'수집 공개분 내 비중'} · 자료 없는 기간은 선을 끊습니다. 공개 목록 부재는 0으로 표시하며 실제 미보유를 확정하지 않습니다.`;
  if(!h){$('pa-chart').innerHTML='이 기관의 수집 자료에 없는 코드입니다.';$('pa-history').innerHTML='';return}
  const max=Math.max(1,...points.map(p=>p.y||0));let last=null,lines='';for(let n=0;n<points.length;n++){const p=points[n],x=45+n*87,y=185-(p.y||0)/max*145;if(p.y==null){last=null;continue}if(last)lines+=`<line x1="${last.x}" y1="${last.y}" x2="${x}" y2="${y}" stroke="#7656ac" stroke-width="3"/>`;lines+=`<circle cx="${x}" cy="${y}" r="4" fill="#7656ac"><title>${p.p}: ${num(p.y)}</title></circle>`;last={x,y}}
  $('pa-chart').innerHTML=`<svg viewBox="0 0 700 235" role="img" aria-label="${esc(i.name+' '+h.name)} 보유 추이"><text x="5" y="20" font-size="12">${num(max)}${metric==='shares'?'주':'%'}</text><line x1="40" y1="185" x2="660" y2="185" stroke="#ddd"/>${lines}${points.map((p,n)=>`<text x="${45+n*87}" y="215" text-anchor="middle" font-size="10">${p.p.slice(2)}</text>`).join('')}</svg>`;
  $('pa-history').innerHTML=table(['기준일','공시 보유 주수','비중'],points.map(p=>`<tr><td>${p.p}</td><td>${p.r?num(p.h?.shares||0):'자료 없음'}</td><td>${p.r?num(M.weight(p.h,p.r))+'%':'—'}</td></tr>`).join(''));
 }
 section.addEventListener('click',e=>{const t=e.target.dataset;if(t.trend){$('pa-security').value=t.trend;renderTrend(state.data.find(i=>i.id===state.manager));$('pa-chart').scrollIntoView({behavior:'smooth',block:'center'})}if(t.track||t.untrack){tracked=t.track?[...new Set([...tracked,t.track])]:tracked.filter(x=>x!==t.untrack);try{localStorage.setItem('portfolio-tracked',JSON.stringify(tracked))}catch{}render()}});
 for(const id of ['pa-kind','pa-query','pa-metric','pa-trend-go','pa-watch-refresh'])$(id)[id==='pa-query'?'oninput':id.endsWith('go')||id.endsWith('refresh')?'onclick':'onchange']=render;
 window.addEventListener('portfolio-data',e=>{state=e.detail;render()});
 fetch('./data/portfolio-metadata.json?t='+Date.now(),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(d=>{meta=d;render()}).catch(()=>{});
})();
