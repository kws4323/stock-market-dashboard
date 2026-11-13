(() => {
  const $ = id => document.getElementById(id);
  const escape = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let state = null;
  const names = {foreign:'외국인', institution:'기관', individual:'개인'};
  const money = (value, signed = false) => typeof value === 'number' && Number.isFinite(value)
    ? (signed && value > 0 ? '+' : '') + (value / 1e8).toLocaleString('ko-KR', {minimumFractionDigits:1,maximumFractionDigits:1}) + '억' : '—';
  function render() {
    const day = $('flow-date').value;
    const market = $('flow-market').value;
    const record = state?.history?.[day];
    $('flow-cards').innerHTML = Object.entries(names).map(([key, name]) => {
      const data = record?.markets?.[market]?.[key];
      const color = data?.net > 0 ? 'positive' : data?.net < 0 ? 'negative' : '';
      const rows = data?.topSell || [];
      return `<article class="flow-card"><div class="flow-label">${name}<span>순매수금액</span></div><div class="flow-net ${color}">${money(data?.net, true)}</div><p class="flow-direction">${data ? data.net > 0 ? '순매수 우위' : data.net < 0 ? '순매도 우위' : '매수·매도 균형' : '데이터 연결 대기'}</p><div class="flow-totals"><span>총매수 <b>${money(data?.buy)}</b></span><span>총매도 <b>${money(data?.sell)}</b></span></div><h3>순매도 TOP 5 <small>금액 기준</small></h3>${rows.length ? `<ol class="flow-rank">${rows.map((row, i) => `<li><span class="flow-number">${i+1}</span><div class="flow-stock"><a href="https://finance.naver.com/item/main.naver?code=${encodeURIComponent(row.code)}" target="_blank" rel="noopener">${escape(row.name)}</a><small>${escape(row.code)} · ${escape(row.market)} <span class="flow-streak">${row.streak?.atLeast ? '최소 ' : ''}${Number(row.streak?.days || 1)}거래일 연속</span></small></div><b class="negative">${money(row.net)}</b></li>`).join('')}</ol>` : `<div class="flow-empty">${data ? '순매도 종목이 없습니다.' : '확인된 데이터가 들어오면 표시됩니다.'}</div>`}</article>`;
    }).join('');
    $('flow-basis').textContent = record ? `${day} · ${record.eveningUpdate ? '저녁 재조회 자료' : '장 마감 후 잠정 집계'} · 수집 ${new Date(record.collectedAt).toLocaleString('ko-KR', {timeZone:'Asia/Seoul',hour12:false})} KST` : '데이터 없음 · 미확인 금액은 표시하지 않습니다.';
  }
  async function load() {
    try {
      const response = await fetch('./data/flows.json?t='+Date.now(), {cache:'no-store',signal:AbortSignal.timeout(15000)});
      if (!response.ok) throw Error('수급 자료를 불러오지 못했습니다. 첫 수집·배포를 확인해 주세요.');
      state = await response.json();
      if(state.schemaVersion !== 1 || typeof state.history !== 'object') throw Error('수급 자료 형식 오류');
      const previous = $('flow-date').value;
      const dates = Object.keys(state.history).sort().reverse();
      $('flow-date').innerHTML = dates.length ? dates.map(day=>`<option value="${escape(day)}">${escape(day)}</option>`).join('') : '<option value="">집계 대기</option>';
      if(dates.includes(previous)) $('flow-date').value = previous;
      $('flow-status').textContent = state.message + (state.expectedDate && state.latestDate !== state.expectedDate ? ` · 최신 예정 거래일 ${state.expectedDate} 자료 대기 중` : '');
      $('flow-connect').hidden = state.status !== 'auth_required';
      render();
    } catch(error) { $('flow-status').textContent = error.message; render(); }
  }
  $('flow-market').onchange = render;
  $('flow-date').onchange = render;
  $('refresh').addEventListener('click', load);
  render(); load();
})();
