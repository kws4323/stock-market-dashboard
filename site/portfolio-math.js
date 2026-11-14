(function(root){
 const value=h=>h?(h.jpy??h.usd??0):0;
 const weight=(h,r)=>r&&h?value(h)/((r.totalJpy??r.totalUsd)||1)*100:0;
 function previousPeriod(date,annual=false){const d=new Date(date+'T00:00:00Z');return new Date(Date.UTC(d.getUTCFullYear()-(annual?1:0),d.getUTCMonth()-(annual?0:3)+1,0)).toISOString().slice(0,10)}
 function compare(institution,current,metadata={}){
  if(!current)return {rows:[],reason:'선택 기준일 자료 없음'};
  const expected=previousPeriod(current.period,institution.id==='gpif');
  const before=institution.reports.find(r=>r.period===expected);
  if(!before)return {rows:[],reason:expected+' 이전 비교 자료 없음'};
  const old=new Map(before.holdings.map(h=>[h.id,h])),now=new Map(current.holdings.map(h=>[h.id,h]));
  const rows=[];
  for(const id of new Set([...old.keys(),...now.keys()])){
   const a=old.get(id),b=now.get(id),h=b||a,symbol=metadata.mapping?.[id],m=metadata.symbols?.[symbol];
   let factor=1,checked=m?.splitStatus==='ok'&&m.splitStart<=before.period;
   if(checked)for(const s of m.splits)if(s.date>before.period&&s.date<=current.period)factor*=s.ratio;
   const prev=(a?.shares||0)*factor,delta=(b?.shares||0)-prev;
   let type=!a?'new':!b?'exit':Math.abs(delta)<1e-6?'same':delta>0?'increase':'decrease';
   const canonical=s=>s.toUpperCase().replace(/[^A-Z0-9]/g,'');
   let review=(type==='new'?[...old.values()]:type==='exit'?[...now.values()]:[]).some(x=>x.id!==id&&canonical(x.name)===canonical(h.name));
   rows.push({id,name:h.name,symbol,a,b,prev,delta,factor,checked,review,type,period:current.period,previous:before.period,weight:weight(b,current),weightChange:weight(b,current)-weight(a,before)});
  }
  return {rows,before};
 }
 function overlap(entries){const map=new Map();for(const {institution,result} of entries)for(const r of result.rows){if(r.type!=='new'||r.review)continue;const key=r.period+'|'+r.id;let x=map.get(key);if(!x){x={...r,owners:[]};map.set(key,x)}if(!x.owners.includes(institution.name))x.owners.push(institution.name)}return [...map.values()].filter(x=>x.owners.length>=2).sort((a,b)=>b.period.localeCompare(a.period)||b.owners.length-a.owners.length)}
 const api={value,weight,previousPeriod,compare,overlap};if(typeof module!=='undefined')module.exports=api;else root.PortfolioMath=api;
})(typeof window!=='undefined'?window:globalThis);
