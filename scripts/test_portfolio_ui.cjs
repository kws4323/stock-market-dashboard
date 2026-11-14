const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),path=require('path');
const nodes=new Map();
class Element{
 constructor(id){this.id=id;this.value='';this._html='';this.textContent='';this.dataset={}}
 set innerHTML(v){this._html=v;for(const m of v.matchAll(/id="([^"]+)"/g))if(!nodes.has(m[1]))nodes.set(m[1],new Element(m[1]));if(!this.value){const o=v.match(/<option value="([^"]+)"/);if(o)this.value=o[1]}}
 get innerHTML(){return this._html}insertAdjacentHTML(p,v){this.innerHTML=v+this.innerHTML}addEventListener(){}scrollIntoView(){}
}
const events={};nodes.set('portfolio-analytics',new Element('portfolio-analytics'));nodes.set('inst-manager',new Element('inst-manager'));
const ctx={window:{addEventListener:(n,fn)=>events[n]=fn},document:{getElementById:id=>{if(!nodes.has(id))throw Error('Missing '+id);return nodes.get(id)}},localStorage:{getItem:()=>null,setItem(){}},fetch:async()=>({ok:true,json:async()=>({})}),console,Event:class{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../site/portfolio-math.js'),'utf8'),ctx);
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../site/portfolio-analytics.js'),'utf8'),ctx);
nodes.get('pa-kind').value='all';nodes.get('pa-metric').value='shares';
const report=(period,shares)=>({period,totalUsd:shares*10,holdings:[{id:'A',name:'TEST',usd:shares*10,shares}]});
events['portfolio-data']({detail:{data:[{id:'test',name:'Test',reports:[report('2026-06-30',20),report('2026-03-31',10)]}],fx:{rate:1300},chosen:['test'],period:'latest',manager:'test'}});
assert.ok(nodes.get('pa-changes').innerHTML.includes('TEST'));
assert.ok(nodes.get('pa-chart').innerHTML.includes('<svg'));
assert.ok(nodes.get('pa-sectors').innerHTML.includes('100%'));
assert.ok(nodes.get('pa-history').innerHTML.includes('자료 없음'));
console.log('UI render passed: change table, SVG trend, missing periods, unknown sector coverage');
