import io
import json
import math
import sys
import unittest
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from scripts.free_sources import (parse_feed, parse_house_index, parse_transaction_cells, rank_quotes,
                                  quote_earnings, collect_feeds, free_calendar, topic_for)
from scripts.research import aggregate, combine_filings, load_information_table


class FreeSourceTests(unittest.TestCase):
    cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def test_rss_timezone_excerpt_and_markup(self):
        raw = b'<rss><channel><item><title>Fed interest rates</title><link>https://example.org/a</link><pubDate>Mon, 12 Oct 2026 09:00:00 -0400</pubDate><description>&lt;p&gt;A short description.&lt;/p&gt;</description></item></channel></rss>'
        r = parse_feed(raw, {"publisher":"Fed"}, self.cutoff)[0]
        self.assertEqual(r["published_at"], "2026-10-12T13:00:00+00:00")
        self.assertEqual(r["summary"], "A short description.")
        self.assertEqual(r["impact_tag"], "통화정책")

    def test_atom_uses_article_link_not_media_enclosure(self):
        raw = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Company earnings</title><updated>2026-10-12T00:00:00Z</updated><link href="https://example.org/a"/><link href="https://example.org/image.jpg" rel="enclosure"/><content>Release information</content></entry></feed>'
        r = parse_feed(raw, {"publisher":"Company", "symbol":"TEST"}, self.cutoff)[0]
        self.assertEqual(r["url"], "https://example.org/a")
        self.assertEqual(r["symbol"], "TEST")

    def test_old_or_undated_news_not_relabelled_recent(self):
        raw = b'<rss><channel><item><title>Old</title><link>https://example.org</link><pubDate>2026-01-01T00:00:00Z</pubDate></item><item><title>No time</title><link>https://example.org/b</link></item></channel></rss>'
        self.assertEqual(parse_feed(raw, {"publisher":"Company"}, self.cutoff), [])

    def test_topic_uses_word_boundaries(self):
        self.assertEqual(topic_for("Corporate spoiler release"), "기업 발표")

    def test_house_zip_selects_only_ptr_and_valid_ids(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            z.writestr('2026FD.txt', 'First\tLast\tFilingType\tFilingDate\tDocID\nA\tB\tP\t10/12/2026\t123\nA\tB\tC\t10/12/2026\t124\nA\tB\tP\tbad\t125\n')
        result = parse_house_index(output.getvalue(), 2026)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['link'].endswith('/2026/123.pdf'))

    def document(self):
        return {"document_id":"123","disclosureDate":"2026-10-12"}

    def cells(self):
        return ['', 'JT', 'Example Common Stock (TEST) [ST]', 'S (partial)', '10/01/2026', '10/05/2026', '$1,001 - $15,000', '']

    def test_ptr_keeps_reported_amount_and_source_row(self):
        result = parse_transaction_cells(self.cells(), self.document(), 2, 3)
        self.assertEqual(result['symbol'], 'TEST')
        self.assertEqual(result['amount'], '$1,001 - $15,000')
        self.assertEqual(result['type'], '매도 (일부)')
        self.assertEqual(result['row_id'], '123:2:3')
        self.assertNotIn('weight_pct', result)

    def test_ptr_rejects_unknown_types_or_impossible_dates(self):
        cells = self.cells(); cells[3] = 'UNKNOWN'
        self.assertIsNone(parse_transaction_cells(cells, self.document(), 1, 1))
        cells = self.cells(); cells[4] = '10/20/2026'
        self.assertIsNone(parse_transaction_cells(cells, self.document(), 1, 1))

    def test_rank_quotes_filters_currency_funds_preferred_and_classes(self):
        def quote(symbol, name, cap, currency='USD', kind='EQUITY'):
            return dict(symbol=symbol, longName=name, marketCap=cap, currency=currency, quoteType=kind)
        us = [quote('A','Same Class A',100),quote('B','Same Class B',90),quote('C','Fund',200,kind='ETF'),quote('D','Other',80)]
        self.assertEqual([r['symbol'] for r in rank_quotes(us,'US',300)],['A','D'])
        kr = [quote('005930.KS','Samsung',100,'KRW'),quote('005935.KS','Samsung preferred',90,'KRW')]
        self.assertEqual(len(rank_quotes(kr,'KR',100)),1)

    def test_estimated_date_range_is_not_a_single_confirmed_date(self):
        timestamp = lambda d: int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())
        q = dict(symbol='TEST',earningsTimestampStart=timestamp('2026-10-20T20:00:00'),earningsTimestampEnd=timestamp('2026-10-22T20:00:00'),exchangeTimezoneName='America/New_York')
        self.assertIsNone(quote_earnings(q,'2026-10-01','2027-01-01'))
        q['earningsTimestampEnd'] = q['earningsTimestampStart']
        self.assertEqual(quote_earnings(q,'2026-10-01','2027-01-01')['date'],'2026-10-20')

    def test_nonfinite_portfolio_values_are_rejected(self):
        with self.assertRaises(ValueError):
            aggregate([dict(value=math.nan,shares=1)],{})

    def test_restatement_replaces_and_addition_appends(self):
        row = lambda c: dict(cusip=c, value=1, shares=1)
        filings = [dict(rows=[row('OLD')],amendment_type='',source_url='a'),dict(rows=[row('NEW')],amendment_type='RESTATEMENT',source_url='b'),dict(rows=[row('EXTRA')],amendment_type='NEW HOLDINGS',source_url='c')]
        rows, sources = combine_filings(filings)
        self.assertEqual([r['cusip'] for r in rows], ['NEW','EXTRA'])
        self.assertEqual(sources,['a','b','c'])
        filings.append(dict(rows=[row('NEW')],amendment_type='NEW HOLDINGS',source_url='d'))
        with self.assertRaises(ValueError): combine_filings(filings)

    def test_sec_cover_total_catches_truncated_table(self):
        class Client:
            def sec(self,url):
                if url.endswith('primary.xml'):
                    return b'<form><tableEntryTotal>2</tableEntryTotal><tableValueTotal>10</tableValueTotal></form>'
                return json.dumps({'directory':{'item':[]}}).encode()
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            load_information_table(Client(),'1',dict(accessionNumber='0000000001-26-000001',primaryDocument='primary.xml',filingDate='2026-10-12'))

    def test_one_country_failure_does_not_destroy_other_country(self):
        def universe(yf,country,target):
            if country=='KR': raise ValueError('unavailable')
            return [dict(symbol='TEST',name='Test',rank=1,quote={'symbol':'TEST'})]
        with patch.dict(sys.modules,{'yfinance':SimpleNamespace()}), patch('scripts.free_sources.yahoo_universe',side_effect=universe):
            result=free_calendar(None,{},None)
        self.assertEqual(result['countries']['KR']['status'],'error')
        self.assertEqual(result['countries']['US']['covered'],1)


if __name__ == '__main__': unittest.main()
