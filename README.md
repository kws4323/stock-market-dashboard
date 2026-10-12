# Stock DashBoard

Static GitHub Pages dashboard with white/violet UI, SEC 13F research, congressional PTR, news headline briefs and a 90-day earnings calendar.

## Deployment

Existing Pages deployment stays `main / (root)`. The existing three scheduled updates remain unchanged: 06:30, 11:40 and 18:00 Asia/Seoul (GitHub can delay scheduled runs). Merge the feature branch, then run **Update market dashboard** manually to verify provider access. No browser-side API keys.

Repository Settings → Secrets and variables → Actions:

| Setting | Kind | Purpose |
| --- | --- | --- |
| `SEC_USER_AGENT` | Secret | SEC-required identifying user agent, e.g. your application name and a real contact email you control |
| `FMP_API_KEY` | Secret | FMP plan with access to screener, calendar, news and congressional endpoints |
| `FMP_PUBLIC_REDISTRIBUTION` | Variable | Set exactly `true` only after confirming your contract permits publishing these fields in a public GitHub repository and website |

No provider credentials or redistribution rights were available during implementation. Unconfigured sections deliberately show no invented records. A provider error preserves the last successful licensed snapshot with its original timestamp and a stale label. Disabling the publication gate removes the provider snapshot on the next run. Historical Git commits can retain previously published data; do not enable the gate before checking the contract.

## Implemented stages and current limits

1. **UI and existing market feed:** responsive white/violet design, Stock DashBoard title, accessible labels, selectable chart plus textual price history. Existing unofficial Yahoo Finance market feed remains, with per-market failure status and price dates. This feed's redistribution rights also need separate review.
2. **SEC institutional research:** four explicitly configured managers in `config/tracking.json`. SEC submissions API and original XML information tables for two adjacent reporting quarters. Changes describe reported share counts, not inferred trades. Links to both original filings, report date and filing date are shown. CUSIP/company-name search covers collected holdings. Ticker search initially supports the eight security mappings in the configuration; unrecognized tickers are not evidence of no ownership. Add validated mappings to expand coverage. Recent submissions lacking two quarters are excluded rather than guessed. Amendments require manual reconciliation and are excluded. No full historical SEC backfill yet.
3. **Congressional PTR:** FMP latest 100 House and 100 Senate records, separately labeled. Shows available trade/disclosure dates, owner, reported amount range and original document links. Missing original links are not fabricated. Transaction disclosures cannot establish current portfolios or portfolio weights. The STOCK Act reporting deadline is generally 30 days after notice and no later than 45 days after transaction, with potential late filings; verify each document. Official House/Senate access/use restrictions also apply.
4. **News:** licensed FMP stock and general feeds, source links and publication dates. The initial brief is a **headline digest**, not a full-text or LLM summary. No article bodies are copied; keyword tags do not establish causal market impact. Stock news is limited to `news_symbols` in configuration. A licensed full-text summarization provider and independent fact checking remain future work.
5. **Earnings:** FMP country screener and 90-day earnings-calendar API. Rank eligible locally listed company records by provider market cap (ETF/fund excluded, same company name deduplicated using the largest line). US: NYSE/NASDAQ/AMEX; KR: KSC/KOE/KOSPI/KOSDAQ. This is provider-universe coverage, **not a verified complete KRX/US exchange census**. A 10,000-row cap is rejected as truncated. Lists all selected companies, missing schedules and actual coverage against KR100/US300 targets. An unconfirmed provider date is not an issuer-confirmed announcement. If KR coverage is incomplete, a licensed KRX/issuer-IR calendar source and identifier reconciliation are required before claiming complete Korean top-100 coverage.

## Calculation rules

- Holding ratio: unique managers with positive reported common-share exposure / successfully collected managers **in the selected report quarter**. Failed managers and different quarters are excluded; configured/success/failed counts are visible. PTR never enters this denominator.
- Portfolio weight: common-share row value / sum of **all** information-table values in that filing. Cash, short positions and assets outside 13F are absent. Option rows remain in the denominator and are excluded from common-share ownership. Shares are aggregated by CUSIP across reported rows.
- Changes: current versus adjacent previous-quarter shares by CUSIP; new, exit, increase, decrease or unchanged. Stock splits and corporate actions are not adjusted.
- Values changed from thousands to dollars in SEC's 2023 format. Within-filing weights are unit invariant; this implementation does not compare raw value totals across filings or publish misleading cross-era totals.
- Snapshot collection timestamps are separate from report/price/transaction/publication dates. Cached data is never relabeled as newly collected after a provider error.

## Validation

Run `python -m unittest discover -s tests -v` and `node --check app.js`.
The collector and tests use only the Python standard library; the existing market updater requires `requirements.txt`. CI checks run on pull requests and feature branch pushes. Scheduled updates run collector tests before writing the research snapshot. Offline fixture tests do not establish API entitlement, current schema or actual Korean coverage; those require the configured workflow's first successful run.

## Primary references

- [SEC submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC automated access](https://www.sec.gov/about/developer-resources)
- [SEC 13F FAQ: timing, scope, dollar units](https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f)
- [FMP API documentation](https://site.financialmodelingprep.com/developer/docs): `company-screener`, `earnings-calendar`, `news/stock`, `news/general-latest`, `house-latest`, `senate-latest`
- [FMP terms](https://site.financialmodelingprep.com/terms-of-service)
- [House original disclosures](https://disclosures-clerk.house.gov/FinancialDisclosure)
- [Senate original disclosures](https://efdsearch.senate.gov/search/)
