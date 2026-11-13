(() => {
 const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let data=[],fx=null,chosen=new Set(),ready=false;
 const report=i=>$('inst-period').value==='latest'?i.reports[0]:i.reports.find(r=>r.period===$('inst-period').value);
 const won=v=>!fx?'환율 확인 불가':v*fx.rate>=1e12?(v*fx.rate/1e12).toLocaleString('ko-KR',{maximumFractionDigits:2})+'조 원':(v*fx.rate/1e8).toLocaleString('ko-KR',{maximumFractionDigits:2})+'억 원';
 const exact=v=>fx?Math.round(v*fx.rate).toLocaleString('ko-KR')+'원':'';
 function tab(which){for(const x of ['market','institution']){$(x+'-view').hidden=x!==which;$(x+'-tab').setAttribute('aria-selected',String(x===which))}if(which==='institution'&&!ready)load();if(which==='market')window.dispatchEvent(new Event('resize'))}
 $('market-tab').onclick=()=>tab('market');$('institution-tab').onclick=()=>tab('institution');
 function common(){
  const active=data.filter(i=>chosen.has(i.id)), available=active.filter(i=>report(i));
  const map=new Map();
  for(const i of available)for(const h of report(i).holdings){if(h.usd<=0)continue;let x=map.get(h.id);if(!x){x={...h,usd:0,owners:[]};map.set(h.id,x)}x.usd+=h.usd;x.owners.push(i.name)}
  const min=$('inst-min').value==='all'?active.length:Number($('inst-min').value), q=$('inst-search').value.toLowerCase();
  const rows=[...map.values()].filter(h=>h.owners.length>=Math.max(2,min)&&(!q||(h.name+' '+h.id).toLowerCase().includes(q))).sort((a,b)=>b.owners.length-a.owners.length||b.usd-a.usd);
  $('inst-summary').innerHTML=`<div><strong>${active.length}</strong>선택 기관</div><div><strong>${available.length}</strong>해당 기준일 자료 확보</div><div><strong>${rows.length}</strong>공통 보유 증권</div>`;
  $('inst-coverage').textContent=`${$('inst-period').value==='latest'?'기관별 최신 공개분을 비교합니다. 보유 기준일이 서로 다를 수 있습니다.':'동일 보유 기준일 '+$('inst-period').value+' 자료만 비교합니다.'} 자료 없는 기관: ${active.filter(i=>!report(i)).map(i=>i.name).join(', ')||'없음'}. 미확인은 미보유를 의미하지 않습니다.`;
  $('inst-common').innerHTML=rows.length?rows.map(h=>`<tr><td>${esc(h.name)}<small>${esc(h.class)} · ${esc(h.id)}</small></td><td>${h.owners.length}곳<small>${h.owners.map(esc).join(' · ')}</small></td><td title="${exact(h.usd)}">${won(h.usd)}</td></tr>`).join(''):'<tr><td colspan="3" class="inst-empty">조건에 맞는 공통 보유종목이 없습니다. 기관·기간 선택 또는 자료 수집 상태를 확인해 주세요.</td></tr>';
 }
 function portfolio(){
  const i=data.find(x=>x.id===$('inst-manager').value);if(!i)return;
  const r=report(i),q=$('inst-holding-search').value.toLowerCase();
  $('inst-detail').textContent=i.scope+(r?` · 보유 기준 ${r.period} · 최종 공시 ${r.filed} · 공개분 합계 ${won(r.totalUsd)} · ${r.holdings.length.toLocaleString()}개 증권`:' · 해당 기간의 수집된 보유자료 없음');
  $('inst-sources').innerHTML=r?r.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.filed)} ${esc(s.form)} 원문 ↗</a>`).join(' · '):`<a href="${esc(i.url)}" target="_blank" rel="noopener">공식 공개자료 확인 ↗</a>`;
  const holdings=(r?.holdings||[]).filter(h=>(h.name+' '+h.id).toLowerCase().includes(q));
  $('inst-holdings').innerHTML=holdings.length?holdings.map((h,n)=>`<tr><td>${n+1}. ${esc(h.name)}<small>${esc(h.class)} · ${esc(h.id)}</small></td><td>${r.totalUsd?(h.usd/r.totalUsd*100).toFixed(2):'0.00'}%</td><td title="${exact(h.usd)}">${won(h.usd)}</td><td>${h.shares.toLocaleString('ko-KR')}</td></tr>`).join(''):'<tr><td colspan="4" class="inst-empty">표시할 보유종목이 없습니다.</td></tr>';
 }
 function render(){common();portfolio()}
 async function load(){
  $('inst-status').textContent='기관 공시 자료를 불러오는 중입니다.';
  try{
   const response=await fetch('./data/institutions.json?t='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('기관 자료 수집을 아직 완료하지 못했습니다.');data=(await response.json()).institutions;
   try{const res=await fetch('./data/market.json?t='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error();const m=(await res.json()).quotes['KRW=X'].meta;const rate=Number(m.regularMarketPrice),time=Number(m.regularMarketTime);if(!(rate>0&&time>0))throw Error();fx={rate,time};}catch{fx=null}
   if(!ready){chosen=new Set(data.map(i=>i.id));$('inst-manager').innerHTML=data.map(i=>`<option value="${i.id}">${esc(i.name)}</option>`).join('');$('inst-manager').value='berkshire'}
   const selectedPeriod=$('inst-period').value;const periods=[...new Set(data.flatMap(i=>i.reports.map(r=>r.period)))].sort().reverse();$('inst-period').innerHTML='<option value="latest">기관별 최신 공개분</option>'+periods.map(p=>`<option>${p}</option>`).join('');if(periods.includes(selectedPeriod))$('inst-period').value=selectedPeriod;
   $('inst-selectors').innerHTML=data.map(i=>`<label><input type="checkbox" value="${i.id}" ${chosen.has(i.id)?'checked':''}>${esc(i.name)}</label>`).join('');
   $('inst-fx').textContent=fx?`환산: 1 USD = ${fx.rate.toLocaleString('ko-KR',{maximumFractionDigits:2})}원 · 환율 관측 ${new Date(fx.time*1000).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})} KST · Yahoo Finance USD/KRW. 분기 말 달러 평가액을 이 환율로 환산한 값이며 현재 평가액·당시 원화 평가액이 아닙니다.`:'환율을 확인하지 못해 원화 금액을 표시하지 않습니다.';
   $('inst-directory').innerHTML=data.map(i=>`<article><h3>${esc(i.name)}<span class="inst-pill">${i.status==='ok'?'공시 연결':i.status==='stale'?'갱신 실패 · 이전 자료':i.status==='error'?'수집 실패':'정량 비교 미연결'}</span></h3><p>${esc(i.group)} · ${esc(i.frequency)}${i.checked?' · 확인 '+esc(i.checked):''}</p><p>${esc(i.scope)}</p><p>${i.reports[0]?'보유 기준 '+esc(i.reports[0].period):'보유 금액·종목 미표시'}</p><a target="_blank" rel="noopener" href="${esc(i.url)}">공식 자료 ↗</a></article>`).join('');
   $('inst-status').textContent=`20개 기관 중 ${data.filter(i=>i.reports.length).length}개 기관의 공개 보유자료를 표시합니다. 공시 확인은 하루 한 번, 새로고침은 저장된 자료를 다시 불러옵니다.`;
   ready=true;render();
  }catch(e){$('inst-status').textContent=e.message}
 }
 $('inst-selectors').onchange=e=>{if(e.target.checked)chosen.add(e.target.value);else chosen.delete(e.target.value);common()};
 $('inst-all').onclick=()=>{chosen=new Set(data.map(i=>i.id));document.querySelectorAll('#inst-selectors input').forEach(x=>x.checked=true);common()};
 $('inst-none').onclick=()=>{chosen.clear();document.querySelectorAll('#inst-selectors input').forEach(x=>x.checked=false);common()};
 $('inst-period').onchange=render;$('inst-min').onchange=common;$('inst-search').oninput=common;$('inst-manager').onchange=portfolio;$('inst-holding-search').oninput=portfolio;$('inst-refresh').onclick=load;
})();
