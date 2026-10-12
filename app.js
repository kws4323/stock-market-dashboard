'use strict';
const $ = id => document.getElementById(id);
const model = DashboardModel;
const fmt = n => n == null || !Number.isFinite(Number(n)) ? '미확인' : Number(n).toLocaleString('ko-KR', {maximumFractionDigits: 2});
const changeNames = {new: '신규', exit: '전량 제외', increase: '증가', decrease: '감소', unchanged: '동일'};
let research = null, marketSnapshot = null, selectedMarket = null, exportContext = null;

function readPreference(key) {
  try {
    const value = JSON.parse(localStorage.getItem('stock-dashboard:' + key) || '[]');
    return Array.isArray(value) ? [...new Set(value.filter(x => typeof x === 'string' && x.length <= 100))].slice(0, 32) : [];
  } catch { return []; }
}
let favorites = readPreference('favorites'), recentSearches = readPreference('recent-searches');
function savePreference(key, value) {
  try { localStorage.setItem('stock-dashboard:' + key, JSON.stringify(value)); }
  catch { $('preferences-status').textContent = '브라우저 저장을 사용할 수 없어 이번 방문 중에만 유지됩니다.'; }
}
function timeLabel(value) {
  if (!value) return '미확인';
  if (!/(?:Z|[+-]\d\d:\d\d)$/.test(value)) return value + ' (제공처 시각)';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '미확인' : new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul', dateStyle: 'medium', timeStyle: 'short'
  }).format(d) + ' KST';
}
function node(tag, text, cls) {
  const n = document.createElement(tag);
  if (text != null) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function link(text, url) {
  const a = node('a', text);
  try {
    const u = new URL(url);
    if (u.protocol === 'https:') { a.href = u.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
  } catch {}
  return a;
}
function empty(root, text) { root.replaceChildren(node('p', text, 'empty')); }
function table(root, headers, rows) {
  const wrap = node('div', null, 'table-wrap'), t = node('table'), head = node('thead'), tr = node('tr');
  headers.forEach(h => { const th = node('th', h); th.scope = 'col'; tr.append(th); });
  head.append(tr); t.append(head);
  const body = node('tbody');
  rows.forEach(row => {
    const tr = node('tr');
    row.forEach(value => { const td = node('td'); td.append(value instanceof Node ? value : node('span', value)); tr.append(td); });
    body.append(tr);
  });
  t.append(body); wrap.append(t); root.append(wrap);
}
function section(name, root) {
  const s = research?.sections?.[name];
  if (!s || s.status === 'not_configured') { empty(root, '실데이터 연결 예정 · API 설정은 마지막 단계에서 진행합니다.'); return null; }
  root.replaceChildren();
  if (s.status !== 'ok') root.append(node('p', `수집 ${s.status === 'stale' ? '실패 · 이전 자료 표시' : '오류'} · ${s.error || ''}`, 'empty'));
  if (s.updated_at) root.append(node('p', '최근 성공 수집: ' + timeLabel(s.updated_at), 'muted'));
  return s.data;
}
function plot(m) {
  selectedMarket = m.symbol;
  const c = $('chart'), x = c.getContext('2d'), p = m.history || [];
  $('chart-title').textContent = m.name + ' · 최근 거래일 종가';
  $('chart-data').textContent = p.length ? p.map(z => `${z.date}: ${fmt(z.close)}`).join(' / ') : '표시할 가격 기록이 없습니다.';
  x.clearRect(0, 0, c.width, c.height);
  if (p.length < 2) return;
  const v = p.map(z => z.close), lo = Math.min(...v), span = Math.max(...v) - lo || 1;
  x.strokeStyle = '#7445d6'; x.lineWidth = 3; x.beginPath();
  p.forEach((z, i) => {
    const xx = 25 + i * (c.width - 50) / (p.length - 1), yy = 170 - (z.close - lo) / span * 140;
    i ? x.lineTo(xx, yy) : x.moveTo(xx, yy);
  });
  x.stroke();
}
function renderMarkets(data = marketSnapshot) {
  if (!data) return;
  marketSnapshot = data;
  $('status').textContent = '시장 수집 시도: ' + timeLabel(data.updated_at);
  const root = $('markets'); root.replaceChildren();
  const displayed = model.filterMarkets(data.markets || [], {
    favorites, onlyFavorites: $('favorites-only').checked,
    category: $('market-category').value, sort: $('market-sort').value
  });
  if (!displayed.length) empty(root, '표시할 지표가 없습니다. 관심 지표를 별표로 저장하거나 필터를 변경하세요.');
  displayed.forEach(m => {
    const card = node('article', null, 'card'), heading = node('div', null, 'card-heading');
    const favorite = node('button', favorites.includes(m.symbol) ? '★' : '☆', 'favorite');
    favorite.setAttribute('aria-label', m.name + ' 관심 지표');
    favorite.setAttribute('aria-pressed', String(favorites.includes(m.symbol)));
    favorite.onclick = () => {
      favorites = favorites.includes(m.symbol) ? favorites.filter(s => s !== m.symbol) : [...favorites, m.symbol].slice(-32);
      savePreference('favorites', favorites); renderMarkets();
    };
    heading.append(node('small', m.name), favorite);
    const change = m.change_pct;
    card.append(heading, node('strong', fmt(m.close)), node('p', change == null ? '등락률 미확인' : (change > 0 ? '+' : '') + fmt(change) + '%', change > 0 ? 'up' : change < 0 ? 'down' : 'muted'));
    card.append(node('small', `${m.history?.at(-1)?.date || '가격일 미확인'} · ${m.status === 'stale' ? '수집 실패 / 이전 자료' : m.source || '출처 미확인'}`));
    const b = node('button', '추이 보기'); b.onclick = () => plot(m);
    card.append(node('p'), b); root.append(card);
  });
  if (!selectedMarket && data.markets?.length) plot(data.markets[0]);
}
function digest(root, data) {
  if (!data) return;
  if (!data.length) { root.append(node('p', '조건에 맞는 기사가 없습니다.', 'empty')); return; }
  data.slice(0, 9).forEach(r => {
    const c = node('article', null, 'card');
    c.append(node('small', `${r.publisher || '출처 미확인'} · ${timeLabel(r.published_at)}`), node('h3', r.title), node('p', r.impact_tag, 'badge'), link('기사 원문 ↗', r.url));
    if (r.summary) c.insertBefore(node('p', r.summary, 'feed-summary'), c.lastChild);
    if (r.watch_point) c.append(node('p', r.watch_point, 'muted'));
    if (r.stale) c.append(node('p', '이번 수집 실패 · 이전 자료', 'note'));
    root.append(c);
  });
  if (data.length > 9) {
    const more = node('button', `더 보기 · 남은 ${data.length - 9}건`, 'secondary');
    more.onclick = () => { more.remove(); digest(root, data.slice(9)); };
    root.append(more);
  }
}

function sourceStatus() {
  const root = $('source-status'); root.replaceChildren();
  if (research.mode === 'free') { $('data-mode').hidden = false; $('data-mode').textContent = '무료 데이터 · 공식 원문 + 무료 제공처'; }
  const sources = (research.sources || []).map(s => [link(s.name, s.url), s.status === 'ok' ? `수집 성공 · ${s.count ?? ''}건` : s.status === 'stale' ? '이전 자료' : '접근 실패', timeLabel(s.collected_at)]);
  for (const m of research.sections?.institutions?.data || []) sources.push([
    m.name + ' · SEC', m.status === 'ok' ? `${m.period} 분기` : m.error || '수집 실패', timeLabel(m.collected_at)
  ]);
  const ptrMeta = research.sections?.ptr?.meta;
  if (ptrMeta) sources.push(['미국 하원 PTR', `${ptrMeta.selected_documents}개 문서 선택 · 상원 미수집`, timeLabel(ptrMeta.collected_at)]);
  const countries = research.sections?.calendar?.data?.countries || {};
  for (const [country, c] of Object.entries(countries)) sources.push([`${country} 시총·일정`, c.status === 'error' ? c.error : `${c.covered}개 종목 · ${c.events.length}개 일정 / Yahoo 비공식`, timeLabel(c.collected_at)]);
  if (sources.length) table(root, ['출처', '수집 범위 / 상태', '최근 수집'], sources);
  else empty(root, '연결된 데이터 출처가 없습니다.');
}
function marketNews() {
  const root = $('market-news'), data = section('market_news', root);
  if (!data) { $('news-count').textContent = ''; return; }
  const q = $('news-query').value.trim().toUpperCase(), topic = $('news-topic').value;
  const filtered = data.filter(r => (!topic || r.impact_tag === topic) &&
    (!q || `${r.title} ${r.publisher || ''}`.toUpperCase().includes(q)))
    .sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''));
  $('news-count').textContent = `${filtered.length} / ${data.length}건 · 최신순`;
  digest(root, filtered);
}
function renderRecentSearches() {
  const root = $('recent-searches'); root.replaceChildren();
  if (!recentSearches.length) return;
  root.append(node('small', '최근 검색'));
  recentSearches.forEach(q => {
    const b = node('button', q, 'chip');
    b.onclick = () => { $('symbol').value = q; search(true); };
    root.append(b);
  });
  const clear = node('button', '기록 지우기', 'chip');
  clear.onclick = () => { recentSearches = []; savePreference('recent-searches', []); renderRecentSearches(); };
  root.append(clear);
}
function stockNews(query) {
  const root = $('stock-news'), data = section('stock_news', root);
  if (!data) return;
  const q = query.toUpperCase();
  digest(root, q ? data.filter(r => r.symbol?.toUpperCase() === q) : data);
}
function search(remember = false, selectedCusip = null) {
  const root = $('search-results'), q = $('symbol').value.trim().slice(0, 100);
  root.replaceChildren(); $('security-choice').hidden = true;
  if (remember && q) {
    recentSearches = [q, ...recentSearches.filter(s => s.toUpperCase() !== q.toUpperCase())].slice(0, 8);
    savePreference('recent-searches', recentSearches); renderRecentSearches();
  }
  // News search remains usable even if institutional collection is unavailable.
  stockNews(q);
  if (!q) { empty(root, '종목을 검색하면 보유기관 비율과 분기별 주식수 변동을 확인할 수 있습니다.'); return; }
  const s = research?.sections?.institutions;
  if (s?.status !== 'ok') { empty(root, '기관 데이터 연결 후 보유비율을 확인할 수 있습니다. 검색 기록은 저장되었습니다.'); return; }
  const result = model.holdingsSearch(s.data || [], $('period').value, q, selectedCusip);
  if (!result.managers.length) { empty(root, '선택한 분기에 정상 수집된 기관이 없습니다.'); return; }
  if (!result.securities.length) { empty(root, '일치하는 공시 증권을 찾지 못했습니다. 티커 매핑 누락 가능성이 있으니 회사명이나 CUSIP으로도 검색하세요.'); return; }
  if (result.securities.length > 1) {
    $('security-choice').hidden = false;
    const options = [Object.assign(node('option', '비율을 확인할 증권을 선택하세요'), {value: ''}),
      ...result.securities.map(h => Object.assign(node('option', `${h.issuer} · ${h.symbol || h.cusip}`), {value: h.cusip}))];
    $('security').replaceChildren(...options); $('security').value = result.selected || '';
    if (!result.selected) { empty(root, '여러 증권이 검색되었습니다. 하나를 선택하면 해당 증권만의 보유기관 비율을 계산합니다.'); return; }
  }
  const security = result.securities.find(h => h.cusip === result.selected);
  if (security.symbol) stockNews(security.symbol);
  root.append(node('h3', `${security.issuer} · ${result.held} / ${result.managers.length}개 기관 보유 · ${fmt(result.ratio)}%`),
    node('p', '분모: ' + result.managers.map(m => m.name).join(', '), 'muted'));
  table(root, ['기관 / 증권', '13F 비중', '주식수', '변동', '전분기 대비 주식수', '공시일 / 원문'],
    result.matches.map(({m, h}) => [m.name + ' / ' + (h.symbol || h.cusip), fmt(h.weight_pct) + '%', fmt(h.shares), changeNames[h.change], fmt(h.share_change), link(m.filed_at, m.source_url)]));
}
function institutions() {
  const root = $('institutions'), data = section('institutions', root);
  $('period').disabled = !data?.some(m => m.status === 'ok');
  if (!data) { $('coverage').textContent = ''; return; }
  const periods = [...new Set(data.filter(m => m.status === 'ok').map(m => m.period))].sort().reverse();
  $('period').replaceChildren(...periods.map(p => Object.assign(node('option', p), {value: p})));
  $('coverage').textContent = `추적 대상 ${data.length}개 · 정상 ${data.filter(m => m.status === 'ok').length}개 · 오류 ${data.filter(m => m.status !== 'ok').length}개. 분기별로 분모가 달라질 수 있습니다.`;
  data.forEach(m => {
    const c = node('article', null, 'card'); c.append(node('h3', m.name));
    if (m.status !== 'ok') c.append(node('p', m.error, 'muted'), link('SEC 공식 원문 조회 ↗', `https://www.sec.gov/edgar/browse/?CIK=${encodeURIComponent(m.cik)}&owner=exclude`));
    else {
      c.append(node('p', `${m.previous_period} → ${m.period}`), link('현재 SEC 원문 ↗', m.source_url), node('p'), link('이전 SEC 원문 ↗', m.previous_source_url));
      m.holdings.filter(h => h.change !== 'unchanged').sort((a, b) => b.weight_pct - a.weight_pct).slice(0, 5)
        .forEach(h => c.append(node('p', `${h.symbol || h.issuer}: ${changeNames[h.change]} · ${fmt(h.weight_pct)}%`)));
    }
    root.append(c);
  });
}
function ptr() {
  const root = $('ptr-data'), data = section('ptr', root);
  if (!data) return;
  const metadata = research.sections.ptr.meta;
  if (metadata) {
    root.append(node('p', `하원 공시 목록 ${metadata.index_documents}건 중 최근 ${metadata.selected_documents}개 문서 확인 · 추출 거래 ${data.length}건 · 상원은 공식 검색 링크로 확인`, 'note'));
    const details = node('details'); details.append(node('summary', '문서별 추출 상태와 원문'));
    const labels = {parsed:'표 추출 완료',partial:'일부 행 미해석',unparsed:'표 미해석',not_current_member:'현직 의원 확인 불가',too_many_pages:'페이지 제한 초과',error:'접근/추출 실패'};
    table(details, ['신고일', '신고인', '추출 상태', '거래 행', '원문'], (metadata.documents || []).map(d => [d.disclosureDate, `${d.firstName} ${d.lastName}`, labels[d.status] || d.status, d.parsed_rows || 0, link('공식 PDF', d.link)]));
    root.append(details);
  }
  const q = $('ptr-query').value.trim().toUpperCase(), chamber = $('ptr-chamber').value;
  const filtered = data.filter(r => (!chamber || r.chamber === chamber) &&
    (!q || `${r.firstName || ''} ${r.lastName || ''} ${r.symbol || ''} ${r.assetDescription || ''}`.toUpperCase().includes(q)));
  root.append(node('p', `표시 ${filtered.length} / ${data.length}건`, 'muted'));
  if (!filtered.length) { root.append(node('p', '조건에 맞는 거래 공시가 없습니다.', 'empty')); return; }
  table(root, ['의원 / 소속', '종목', '거래일', '신고일', '유형 / 소유자', '금액 범위', '공시'], filtered.map(r => [
    `${r.firstName || ''} ${r.lastName || ''} · ${r.chamber === 'house' ? '하원' : '상원'}`, r.symbol || r.assetDescription || '미확인',
    r.transactionDate || '미확인', r.disclosureDate || r.dateRecieved || '미확인', `${r.type || '미확인'} / ${r.owner || '미확인'}`,
    r.amount || '미확인', link(r.page ? `원문 ${r.page}쪽` : '공시 원문', r.link ? r.link + (r.page ? '#page=' + r.page : '') : null)
  ]));
}
function calendar() {
  exportContext = null; $('calendar-csv').disabled = true; $('calendar-ics').disabled = true;
  const root = $('calendar-data'), data = section('calendar', root);
  if (!data) return;
  const country = $('country').value, c = data.countries[country];
  if (!c) { root.append(node('p', '이 시장의 일정 데이터가 없습니다.', 'empty')); return; }
  if (c.status === 'error') { root.append(node('p', c.error || '이 시장의 수집 실패', 'empty')); return; }
  if (c.status === 'stale') root.append(node('p', '이 시장의 이번 수집 실패 · 이전 자료', 'note'));
  root.append(node('p', `${data.from} ~ ${data.to} · 순위 수집 ${timeLabel(data.ranked_at)}`, 'muted'));
  root.append(node('h3', `회사 수록 ${c.covered}/${c.target} · 발표일 미확인 ${c.missing_schedule.length}개`));
  if (!c.coverage_complete) root.append(node('p', c.target_reached ? '목표 종목 수는 수집했으나 무료 제공처의 범위입니다. 공식 거래소의 완전한 회사별 시총 순위로 검증되지 않았습니다.' : '커버리지 부족: 요청한 상위 회사 수를 충족하지 못했습니다. 완전한 전국 시총 순위로 해석할 수 없습니다.', 'note'));
  const from = $('calendar-from').value, to = $('calendar-to').value;
  if (from && to && from > to) { root.append(node('p', '종료일은 시작일 이후로 선택하세요.', 'empty')); return; }
  const filtered = model.filterEarnings(c.events, c.universe, {from, to, query: $('calendar-query').value});
  const names = Object.fromEntries(c.universe.map(r => [r.symbol, r]));
  root.append(node('p', `조건에 맞는 일정 ${filtered.length}건`, 'muted'));
  if (filtered.length) {
    table(root, ['발표 예정일', '제공처 시총 순위', '회사 / 종목', 'EPS 예상', '일정 상태 / 원문'], filtered.map(r => [
      r.date, names[r.symbol]?.rank, `${names[r.symbol]?.name || r.symbol} (${r.symbol})`, fmt(r.eps_estimated), link(r.status === 'official_confirmed' ? '기업 공식 발표 확인' : '제공처 예정 · IR 미확인', r.source_url)
    ]));
    exportContext = {events: filtered, country, universe: c.universe};
    $('calendar-csv').disabled = false; $('calendar-ics').disabled = false;
  } else root.append(node('p', '표시할 예정 일정이 없습니다. 기간·검색 조건을 확인하세요. 일정 미확인 회사가 있을 수 있습니다.', 'empty'));
  const details = node('details'), summary = node('summary', '수집한 회사 전체와 일정 미확인 목록');
  details.append(summary);
  const missing = new Set(c.missing_schedule);
  table(details, ['순위', '회사', '티커', '일정'], c.universe.map(r => [r.rank, r.name, r.symbol, missing.has(r.symbol) ? '일정 미확인' : '일정 수록']));
  root.append(details);
}
function download(content, type, filename) {
  const url = URL.createObjectURL(new Blob([content], {type})), a = node('a');
  a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('search').onsubmit = e => { e.preventDefault(); search(true); };
$('period').onchange = () => search();
$('security').onchange = () => search(false, $('security').value);
['market-category', 'market-sort', 'favorites-only'].forEach(id => $(id).onchange = () => renderMarkets());
$('news-topic').onchange = marketNews; $('news-query').oninput = marketNews;
$('ptr-chamber').onchange = ptr; $('ptr-query').oninput = ptr;
['country', 'calendar-from', 'calendar-to'].forEach(id => $(id).onchange = calendar);
$('calendar-query').oninput = calendar;
$('calendar-reset').onclick = () => { ['calendar-from', 'calendar-to', 'calendar-query'].forEach(id => $(id).value = ''); calendar(); };
$('calendar-csv').onclick = () => {
  if (!exportContext) return;
  const {events, country, universe} = exportContext, names = Object.fromEntries(universe.map(r => [r.symbol, r.name]));
  download(model.toCSV([['발표 예정일', '시장', '회사', '티커', '일정 상태', '원문'], ...events.map(r => [r.date, country, names[r.symbol], r.symbol, r.status === 'official_confirmed' ? '기업 공식 발표 확인' : '제공처 예정 / 회사 IR 미확인', r.source_url || ''])]), 'text/csv;charset=utf-8', `earnings-${country}.csv`);
};
$('calendar-ics').onclick = () => {
  if (!exportContext) return;
  const {events, country, universe} = exportContext;
  download(model.toICS(events, country, universe), 'text/calendar;charset=utf-8', `earnings-${country}.ics`);
};
async function load(path) {
  const r = await fetch(path + '?ts=' + Date.now());
  if (!r.ok) throw Error('데이터 파일을 가져올 수 없습니다');
  return r.json();
}
renderRecentSearches();
load('./data/markets.json').then(renderMarkets).catch(e => $('status').textContent = e.message);
load('./data/research.json').then(data => {
  research = data; sourceStatus(); institutions(); search(); ptr(); calendar();
  const topics = [...new Set((data.sections?.market_news?.data || []).map(r => r.impact_tag).filter(Boolean))].sort();
  topics.forEach(t => $('news-topic').append(Object.assign(node('option', t), {value: t})));
  marketNews();
}).catch(() => ['institutions', 'stock-news', 'market-news', 'ptr-data', 'calendar-data'].forEach(id => empty($(id), '연구 데이터 파일을 불러올 수 없습니다. 다음 자동 업데이트를 확인하세요.')));
