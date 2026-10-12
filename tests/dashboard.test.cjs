const {test} = require('node:test');
const assert = require('node:assert/strict');
const m = require('../dashboard-model.js');
const holding = (cusip, shares = 10, issuer = 'Example', symbol = 'TEST') => ({cusip, shares, issuer, symbol});
const manager = (cik, holdings, extra = {}) => ({cik, name: cik, holdings, status: 'ok', period: '2026-06-30', ...extra});

test('ownership denominator excludes failed managers and other quarters', () => {
  const result = m.holdingsSearch([
    manager('1', [holding('X')]), manager('2', []),
    manager('3', [holding('X')], {status: 'error'}),
    manager('4', [holding('X')], {period: '2026-03-31'})
  ], '2026-06-30', 'TEST');
  assert.equal(result.ratio, 50);
  assert.equal(result.managers.length, 2);
});
test('different securities must never be combined into a single ownership ratio', () => {
  const managers = [manager('1', [holding('X', 10, 'Example One')]), manager('2', [holding('Y', 10, 'Example Two')])];
  const result = m.holdingsSearch(managers, '2026-06-30', 'Example');
  assert.equal(result.ratio, null);
  assert.equal(result.securities.length, 2);
  assert.equal(m.holdingsSearch(managers, '2026-06-30', 'Example', 'X').ratio, 50);
});
test('exited holdings remain searchable but do not count as current owners', () => {
  const result = m.holdingsSearch([manager('1', [holding('X', 0)]), manager('2', [])], '2026-06-30', 'X');
  assert.equal(result.ratio, 0);
  assert.equal(result.matches.length, 1);
});
test('missing mapping or no match is unknown, never a claim of zero ownership', () => {
  const result = m.holdingsSearch([manager('1', [holding('X', 10, 'Example', null)])], '2026-06-30', 'MISSING');
  assert.equal(result.ratio, null);
});
test('duplicate manager entries do not inflate the denominator', () => {
  const result = m.holdingsSearch([manager('1', [holding('X')]), manager('1', [holding('X')])], '2026-06-30', 'TEST');
  assert.equal(result.managers.length, 1);
  assert.equal(result.ratio, 100);
});
test('favorites and country filters intersect and sorting keeps missing values last', () => {
  const rows = [{name: 'KOSPI', symbol: 'A', change_pct: 1}, {name: 'KOSDAQ', symbol: 'B', change_pct: null},
    {name: 'S&P 500', symbol: 'C', change_pct: 3}, {name: 'Gold', symbol: 'D', change_pct: -1}];
  assert.deepEqual(m.filterMarkets(rows, {category: 'KR', favorites: ['B'], onlyFavorites: true}).map(r => r.symbol), ['B']);
  assert.deepEqual(m.filterMarkets(rows, {sort: 'asc'}).map(r => r.symbol), ['D', 'A', 'C', 'B']);
  assert.equal(rows[0].symbol, 'A');
});
test('calendar date boundaries, company-name search and duplicates', () => {
  const rows = [{symbol: 'TEST', date: '2026-10-12'}, {symbol: 'TEST', date: '2026-10-12'}, {symbol: 'TEST', date: '2026-10-13'}, {symbol: 'TEST', date: '2026-02-30'}];
  const universe = [{symbol: 'TEST', name: '한글 회사'}];
  assert.equal(m.filterEarnings(rows, universe, {query: '한글', from: '2026-10-12', to: '2026-10-12'}).length, 1);
  assert.equal(m.filterEarnings(rows, universe, {from: '2026-10-13', to: '2026-10-12'}).length, 0);
  assert.equal(m.filterEarnings(rows, universe, {from: 'invalid'}).length, 0);
});
test('CSV escapes quotes, preserves Korean and neutralizes spreadsheet formulas', () => {
  const csv = m.toCSV([['한글,"회사"', '=HYPERLINK("bad")', ' +SUM(1)', '@evil', '\tmalicious']]);
  assert.ok(csv.startsWith('\ufeff'));
  assert.ok(csv.includes('"한글,""회사"""'));
  assert.ok(csv.includes("'=HYPERLINK"));
  assert.ok(csv.includes("' +SUM"));
  assert.ok(csv.includes("'@evil"));
});
test('ICS emits tentative all-day events with exclusive next-day end across year boundary', () => {
  const ics = m.toICS([{symbol: 'TEST', date: '2026-12-31'}], 'KR', [], new Date('2026-10-12T00:00:00Z'));
  assert.ok(ics.includes('DTSTART;VALUE=DATE:20261231'));
  assert.ok(ics.includes('DTEND;VALUE=DATE:20270101'));
  assert.ok(ics.includes('STATUS:TENTATIVE'));
  assert.ok(ics.includes('DTSTAMP:20261012T000000Z'));
});
test('ICS safely folds long Korean names to at most 75 UTF-8 bytes per physical line', () => {
  const ics = m.toICS([{symbol: 'TEST', date: '2026-10-12'}], 'KR', [{symbol: 'TEST', name: '가나다라'.repeat(40)}]);
  ics.split('\r\n').forEach(line => assert.ok(Buffer.byteLength(line, 'utf8') <= 75));
  assert.ok(ics.replace(/\r\n /g, '').includes('가나다라'.repeat(40)));
});
test('ICS escapes provider text and ignores malformed event dates', () => {
  const ics = m.toICS([{symbol: 'TEST', date: 'invalid'}, {symbol: 'TEST', date: '2026-10-12'}], 'KR', [{symbol: 'TEST', name: 'Name\nBEGIN:VEVENT,semi;slash\\'}]);
  assert.equal(ics.split('\r\nBEGIN:VEVENT\r\n').length, 2);
  assert.ok(ics.includes('Name\\nBEGIN:VEVENT\\,semi\\;slash\\\\'));
});
