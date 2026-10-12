import unittest
from unittest.mock import patch
from scripts.research import aggregate, changes, collect, news, parse_table, ranked, calendar, institution
import json


class ResearchTests(unittest.TestCase):
    def row(self, cusip="X", value=100, shares=10, option=""):
        return dict(cusip=cusip, issuer="Example", value=value, shares=shares, option=option, unit="SH")

    def test_full_denominator_and_duplicate_rows(self):
        result = aggregate([self.row(), self.row(value=50), self.row("Y", 50, option="PUT")], {"X": "TEST"})
        self.assertEqual(result["X"]["weight_pct"], 75)
        self.assertEqual(result["X"]["shares"], 20)
        self.assertNotIn("Y", result)

    def test_new_exit_and_share_changes(self):
        a = aggregate([self.row("X", shares=20), self.row("Y")], {})
        b = aggregate([self.row("X"), self.row("Z")], {})
        result = {r["cusip"]: r for r in changes(a, b)}
        self.assertEqual(result["X"]["change"], "increase")
        self.assertEqual(result["X"]["share_change"], 10)
        self.assertEqual(result["Y"]["change"], "new")
        self.assertEqual(result["Z"]["change"], "exit")
        self.assertEqual(result["Z"]["weight_pct"], 0)

    def test_namespaced_sec_table(self):
        rows = parse_table(b'<informationTable xmlns="urn:sec"><infoTable><nameOfIssuer>Example</nameOfIssuer><cusip>X</cusip><value>100</value><shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable></informationTable>')
        self.assertEqual(rows[0]["shares"], 10)
        with self.assertRaises(ValueError):
            parse_table(b'<empty/>')

    def test_amended_quarter_excluded_before_table_requests(self):
        class Client:
            def sec(self, url):
                if 'submissions' not in url:
                    raise AssertionError('Must not use unmerged amendment')
                return json.dumps({'filings': {'recent': {
                    'form': ['13F-HR/A', '13F-HR', '13F-HR'],
                    'reportDate': ['2026-06-30', '2026-06-30', '2026-03-31'],
                    'filingDate': ['2026-08-15', '2026-08-14', '2026-05-14'],
                    'accessionNumber': ['a', 'b', 'c']}}}).encode()
        with self.assertRaisesRegex(ValueError, 'Amended'):
            institution(Client(), {'cik': '1', 'name': 'Example'}, {})

    def test_headline_digest_deduplicates_and_drops_unsafe_urls(self):
        data = news([dict(title="Fed rates", url="https://example.org"), dict(title="Duplicate", url="https://example.org"), dict(title="Unsafe", url="javascript:alert(1)")])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["summary_method"], "headline_only")
        self.assertNotIn("text", data[0])

    def test_ranking_filters_foreign_etf_and_duplicate_company(self):
        def company(symbol, cap, **kw):
            return dict(symbol=symbol, companyName="Same" if symbol in ("A", "B") else symbol, marketCap=cap, country="US", exchangeShortName="NYSE", **kw)
        rows = [company("A", 200), company("B", 100), company("C", 500, isEtf=True), company("D", 300)]
        self.assertEqual([r["symbol"] for r in ranked(rows, "US", 2)], ["D", "A"])

    @patch.dict("os.environ", {"FMP_PUBLIC_REDISTRIBUTION": "false"})
    def test_unconfigured_never_calls_api(self):
        class Client:
            ua = ""
            key = "secret"
            def fmp(self, *args, **kwargs):
                raise AssertionError("Must not call provider")
        result = collect(Client(), {"institutions": [], "cusips": {}})
        self.assertTrue(all(s["status"] == "not_configured" for s in result["sections"].values()))
        self.assertNotIn("secret", str(result))

    @patch.dict("os.environ", {"FMP_PUBLIC_REDISTRIBUTION": "true"})
    def test_failure_preserves_timestamp_and_labels_stale(self):
        class Client:
            ua = ""
            key = "secret"
            def fmp(self, *args, **kwargs):
                raise RuntimeError("https://example.org?apikey=secret")
        previous = {"sections": {"market_news": {"data": [{"title": "old"}], "updated_at": "old-time"}}}
        result = collect(Client(), {"news_symbols": []}, previous)
        self.assertEqual(result["sections"]["market_news"]["status"], "stale")
        self.assertEqual(result["sections"]["market_news"]["updated_at"], "old-time")
        self.assertNotIn("secret", str(result))

    def test_calendar_marks_insufficient_coverage_and_missing_dates(self):
        class Client:
            def fmp(self, endpoint, **kwargs):
                if endpoint == "earnings-calendar":
                    return []
                country = kwargs["country"]
                return [dict(symbol=country, companyName=country, country=country, marketCap=100, exchangeShortName="KSC" if country == "KR" else "NYSE")]
        result = calendar(Client())
        self.assertFalse(result["countries"]["KR"]["coverage_complete"])
        self.assertEqual(result["countries"]["KR"]["missing_schedule"], ["KR"])


if __name__ == "__main__":
    unittest.main()
