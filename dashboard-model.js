/* Pure view calculations, shared by the browser and Node's test runner. */
(function (root) {
  'use strict';
  const normalized = value => String(value ?? '').trim().toUpperCase();
  const validDate = value => /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(value + 'T00:00:00Z')) &&
    new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;

  function holdingsSearch(institutions, period, query, selectedCusip) {
    const managers = [...new Map(institutions.filter(m => m.status === 'ok' && m.period === period)
      .map(m => [m.cik, m])).values()];
    const q = normalized(query);
    const candidates = new Map();
    for (const m of managers) for (const h of m.holdings || []) {
      if (q && (normalized(h.symbol) === q || normalized(h.cusip) === q || normalized(h.issuer).includes(q))) {
        candidates.set(h.cusip, {cusip: h.cusip, symbol: h.symbol, issuer: h.issuer});
      }
    }
    const securities = [...candidates.values()].sort((a, b) => a.issuer.localeCompare(b.issuer));
    const selected = candidates.has(selectedCusip) ? selectedCusip : securities.length === 1 ? securities[0].cusip : null;
    const matches = selected ? managers.flatMap(m => (m.holdings || [])
      .filter(h => h.cusip === selected).map(h => ({m, h}))) : [];
    const held = new Set(matches.filter(({h}) => h.shares > 0).map(({m}) => m.cik)).size;
    return {managers, securities, selected, matches, held,
      ratio: selected && managers.length ? held / managers.length * 100 : null};
  }

  function filterMarkets(markets, {favorites = [], onlyFavorites = false, category = '', sort = ''} = {}) {
    const categories = {'KOSPI': 'KR', 'KOSDAQ': 'KR', 'S&P 500': 'US', 'NASDAQ Composite': 'US',
      'Russell 2000': 'US', 'Dow Jones': 'US'};
    const result = markets.filter(m => (!onlyFavorites || favorites.includes(m.symbol)) &&
      (!category || (categories[m.name] || 'OTHER') === category));
    if (sort) result.sort((a, b) => {
      const av = a.change_pct, bv = b.change_pct;
      if (av == null) return bv == null ? 0 : 1;
      if (bv == null) return -1;
      return sort === 'asc' ? av - bv : bv - av;
    });
    return result;
  }

  function filterEarnings(events, universe, {query = '', from = '', to = ''} = {}) {
    if ((from && !validDate(from)) || (to && !validDate(to)) || (from && to && from > to)) return [];
    const names = Object.fromEntries(universe.map(r => [r.symbol, r.name]));
    const q = normalized(query);
    const seen = new Set();
    return events.filter(r => {
      const key = `${r.symbol}|${r.date}`;
      if (!validDate(r.date) || seen.has(key) || (from && r.date < from) || (to && r.date > to) ||
        (q && !normalized(`${r.symbol} ${names[r.symbol] || ''}`).includes(q))) return false;
      seen.add(key);
      return true;
    }).sort((a, b) => a.date.localeCompare(b.date) || a.symbol.localeCompare(b.symbol));
  }

  function toCSV(rows) {
    const cell = value => {
      let s = String(value ?? '');
      // Quoting alone does not prevent spreadsheet formula execution.
      if (/^[\s]*[=+@-]|^[\t\r\n]/.test(s)) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    };
    return '\ufeff' + rows.map(row => row.map(cell).join(',')).join('\r\n') + '\r\n';
  }

  function toICS(events, country, universe, timestamp = new Date()) {
    const escape = s => String(s ?? '').replace(/\\/g, '\\\\').replace(/\r\n|\r|\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
    const compact = s => s.replace(/-/g, '');
    const names = Object.fromEntries(universe.map(r => [r.symbol, r.name]));
    const stamp = timestamp.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
    const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Stock DashBoard//Earnings//KO', 'CALSCALE:GREGORIAN'];
    for (const r of filterEarnings(events, universe)) {
      const next = new Date(r.date + 'T00:00:00Z'); next.setUTCDate(next.getUTCDate() + 1);
      lines.push('BEGIN:VEVENT', `UID:${encodeURIComponent(country + '-' + r.symbol + '-' + r.date)}@stock-dashboard.local`,
        `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${compact(r.date)}`,
        `DTEND;VALUE=DATE:${compact(next.toISOString().slice(0, 10))}`,
        `SUMMARY:${escape((names[r.symbol] || r.symbol) + ' 실적 발표 예정')}`,
        `DESCRIPTION:${escape(`${r.symbol} · ${country} · ${r.status === 'official_confirmed' ? '기업 공식 발표 확인' : '제공처 예정일 / 회사 IR 미확인'}. 일정은 변경될 수 있습니다. ${r.source_url || ''}`)}`,
        r.status === 'official_confirmed' ? 'STATUS:CONFIRMED' : 'STATUS:TENTATIVE', 'TRANSP:TRANSPARENT', 'END:VEVENT');
    }
    lines.push('END:VCALENDAR');
    // RFC 5545 line folding counts UTF-8 octets, not JavaScript characters.
    const fold = line => {
      const encoder = new TextEncoder(); let out = '', count = 0;
      for (const char of line) {
        const size = encoder.encode(char).length;
        if (count + size > 75) {out += '\r\n '; count = 1;}
        out += char; count += size;
      }
      return out;
    };
    return lines.map(fold).join('\r\n') + '\r\n';
  }

  function memberKey(r) {
    return JSON.stringify([r.chamber || '', r.firstName || '', r.lastName || '']);
  }
  function filterTrades(rows, options = {}) {
    const q = (options.query || '').trim().toUpperCase();
    return rows.filter(r => (!options.member || memberKey(r) === options.member) &&
      (!options.chamber || r.chamber === options.chamber) &&
      (!options.type || (r.type || '').startsWith(options.type)) &&
      (!options.owner || r.owner === options.owner) &&
      (!options.from || (validDate(r.transactionDate) && r.transactionDate >= options.from)) &&
      (!options.to || (validDate(r.transactionDate) && r.transactionDate <= options.to)) &&
      (!q || `${r.firstName || ''} ${r.lastName || ''} ${r.symbol || ''} ${r.assetDescription || ''}`.toUpperCase().includes(q)))
      .sort((a,b) => (b.transactionDate || '').localeCompare(a.transactionDate || ''));
  }
  function tradeComposition(rows) {
    const grouped = new Map();
    for (const r of rows) {
      const name = r.symbol || r.assetDescription || '종목 미확인';
      grouped.set(name, (grouped.get(name) || 0) + 1);
    }
    return [...grouped].map(([name,count]) => ({name,count,percent: count / rows.length * 100}))
      .sort((a,b) => b.count - a.count || a.name.localeCompare(b.name));
  }
  const api = {holdingsSearch, filterMarkets, filterEarnings, toCSV, toICS, validDate, memberKey, filterTrades, tradeComposition};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.DashboardModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
