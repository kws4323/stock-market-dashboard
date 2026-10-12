# Stock DashBoard

White/violet static GitHub Pages dashboard, with free-source research snapshots and three scheduled updates at 06:30, 11:40 and 18:00 Asia/Seoul. GitHub can delay scheduled runs.

## Default: no subscription keys

`config/tracking.json` sets `free_mode: true`. The default pipeline does **not** call FMP or a paid AI API. Existing unofficial Yahoo Finance market indicators remain. `scripts/research.py` collects research data into `data/research.json`; `scripts/update.py` refreshes market prices. The workflow publishes both files and reuses a short-lived House PDF parsing cache.

| Feature | Source | Scope and limitations |
| --- | --- | --- |
| Institutional holdings | SEC submissions and original 13F XML | Four configured managers, two adjacent quarters, completeness checks against filing entry/value totals. SEC can block a runner; failures are visible and excluded from ownership denominators. |
| Market news | Federal Reserve and BEA RSS, selected company releases | Last 30 days, original source links, feed timestamps, short syndicated excerpts and rule-based topics/watch points. No generated full-text analysis or prediction of market impact. |
| Company news | Apple, Microsoft and NVIDIA official RSS/Atom | Only connected official company feeds; no matching story does not mean no relevant news. Company releases represent the issuer's own position. |
| Congressional PTR | U.S. House Clerk official annual index and PDF tables | Select latest 20 PTR documents. Only PDFs that identify the filer as a Member and supported transaction rows are displayed. Up to eight pages per document; unparsed/partial/skipped document status and PDF page links are shown. Senate remains a manual official search link. |
| Earnings calendar | Yahoo Finance screener quote fields plus verified issuer announcements | Targets KR100/US300 by provider market cap; estimated or unknown dates are labeled. Officially verified issuer dates override conflicting provider dates. This is not a verified complete exchange census. |

Public access to data does not by itself grant unlimited redistribution rights. Review Yahoo terms and issuer feed conditions before commercial reuse. House disclosure records have explicit statutory use restrictions, including restrictions on commercial use. No CAPTCHA, login, or access-control bypass is implemented.

## Optional SEC identification

SEC access needs an identifying User-Agent. The default identifies this repository and its Issues contact URL; there is no invented personal email. If a runner is denied, set the Actions secret `SEC_USER_AGENT` to your application name and a real monitored contact email. This does not guarantee access or override SEC restrictions. The collector limits its request rate and reports access errors honestly. SEC failures do not prevent the news, PTR or earnings sections from updating.

## 13F rules

- Holdings ratio: unique managers holding a positive reported share position / successfully collected managers **in the selected report quarter**. Failed managers, different quarters and congressional PTR are excluded.
- Weight: non-option SH row value / all information-table values in that filing. This is not a share of total assets. Cash, shorts and non-13F assets are absent. Duplicate CUSIP rows are summed.
- Share change is the reported difference versus the adjacent previous quarter; it is not inferred trading volume and is not adjusted for stock splits/corporate actions.
- Original and restatement/additional-holdings amendments are read in filing order. A restatement replaces previous rows. New-holdings additions are accepted only without ambiguous overlapping security/discretion/manager identities. Unknown/overlapping amendments are excluded. All current-quarter original/amendment links are stored.
- Entry count and total reported value must agree with the SEC cover page before calculating ratios. Historical pre-January-2023 values are normalized from thousands to dollars before amendment combination.
- Up to three older SEC submissions archive fragments are checked if the recent block lacks two reporting quarters.
- CUSIP and issuer-name search covers collected rows. Ticker search initially uses the eight explicitly configured CUSIP mappings; missing mappings must not be interpreted as zero ownership. Multiple matching securities require a CUSIP selection.

## News reliability

`config/free_sources.json` lists original feed endpoints. RSS/Atom dates retain their timezone; undated/old stories are excluded. Each entry includes source link, collected/publication timestamps, source type and summary method. Titles and excerpts are bounded; article bodies are not copied. A failed feed can retain its own recent previous entries with a stale marker. Topics and watch points describe things to check, not verified effects or investment advice. No translation/LLM service is called.

## PTR reliability

The House index identifies documents, not individual trades. PDFs are parsed using header column geometry, including merged body rows. A transaction needs a supported P/S/E type, valid date no later than disclosure date and reported amount range. No numerical amount midpoint, current position, profit or portfolio weight is inferred. Owner codes remain explicit (SP spouse, JT joint, DC dependent child). Failed rows are not guessed. The document list states extraction status; successfully parsed documents can still contain unsupported layouts that require source review.

The PDF cache is versioned and lasts at most a day. Amendments normally have separate document IDs. Senate authentication/usage agreements are not automated.

## Earnings reliability

The free Yahoo screener is queried in sorted pages (maximum 250 per request). US queries cover NYSE/Nasdaq/AMEX provider exchanges and USD equities; KR queries cover KSC/KOE provider exchanges and KRW equities. Same company names/share-class suffixes are deduplicated using the largest reported line. Numeric Korean preferred-share codes are excluded. This rule can omit uncommon identifiers; rankings are provider coverage, not official company-level market-cap totals. Full country coverage is never asserted simply because 100/300 rows were returned.

A date is derived in the exchange timezone only when provider start/end dates agree and lie within 90 days. Date ranges are left unconfirmed/missing rather than converted into one guessed day. `isEarningsDateEstimate=false` does not constitute issuer confirmation. `config/free_sources.json` may contain reviewed original issuer announcements; both date and announcement text must still be found in the current original page before overriding provider data. Expired announcements are dropped. The initial override is Microsoft's October 28, 2026 announcement; Yahoo supplied a conflicting date, demonstrating why provenance matters.

Country failures are isolated. Previous data retains its country-specific timestamp and a stale status. Missing schedules are listed separately. CSV and ICS exports include only visible filtered events, their status and source. Officially verified events export as confirmed; provider dates remain tentative. All-day calendar dates do not infer an announcement time, and downloaded calendars do not auto-refresh.

## Browser features

Favorite market indicators, category filters, change sorting, up to eight recent searches, news topic/publisher/headline filters, PTR chamber/person/ticker filters, earnings country/company/inclusive-date filters and CSV/ICS export. Favorites/search history stay in local browser storage; storage failures do not block use. Data collection timestamps display in KST; timezone-less provider times are labeled as such. All provider text is inserted as text, CSV formula-leading cells are neutralized, and ICS strings are escaped/folded by UTF-8 octets.

## Tests and deployment

- `python -m unittest discover -s tests -v`
- `node --test tests/dashboard.test.cjs`
- `node --check app.js`
- Optional browser suite: `npm install`, `npx playwright install chromium`, `npm run test:browser`. `CHROME_PATH` / `PLAYWRIGHT_MODULE` can select installed runtimes. Test-only fixtures never replace published snapshots. Local screenshots/downloads go to ignored `work/`.

PR CI runs Python and JavaScript tests. A separate **Free data source validation** workflow collects a non-published live snapshot and uploads a short-lived artifact. Inspect its provider statuses: a completed job does not mean every external provider succeeded. Existing Pages deployment is `main / (root)`. The three-run updater works without paid credentials.

## Optional legacy FMP mode

Setting `free_mode: false` retains the earlier subscription-based adapters. They require `FMP_API_KEY`, `SEC_USER_AGENT` and `FMP_PUBLIC_REDISTRIBUTION=true` only after confirming public redistribution rights. Those adapters are not used by the default free pipeline.

## Original references

- [SEC automated access](https://www.sec.gov/about/developer-resources) / [SEC 13F FAQ](https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f)
- [Federal Reserve RSS](https://www.federalreserve.gov/feeds/feeds.htm) / [BEA RSS](https://apps.bea.gov/rss/rss.xml)
- [House disclosures and use conditions](https://disclosures-clerk.house.gov/FinancialDisclosure/ViewSearch) / [Senate official search](https://efdsearch.senate.gov/search/)
- [yfinance screener documentation](https://ranaroussi.github.io/yfinance/reference/api/yfinance.screen.html)
- [Microsoft original earnings date announcement](https://news.microsoft.com/source/2026/10/07/microsoft-announces-quarterly-earnings-release-date-69)
