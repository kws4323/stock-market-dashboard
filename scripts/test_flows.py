import unittest
from flows import top_sellers, streak

def entry(codes):
    return {"markets": {"ALL": {"foreign": {"topSell": [{"code": c} for c in codes]}}}}

class FlowTests(unittest.TestCase):
    def test_rank_by_money_and_exclude_buyers(self):
        rows = [{"code": str(i), "net": n} for i, n in enumerate([20, -10, -90, 0, -20, -50, -30, -40])]
        self.assertEqual([r["net"] for r in top_sellers(rows)], [-90, -50, -40, -30, -20])

    def test_weekend_is_not_a_break(self):
        dates = ["2026-11-05", "2026-11-06", "2026-11-09"]
        h = {dates[0]: entry([]), dates[1]: entry(["A"]), dates[2]: entry(["A"])}
        self.assertEqual(streak(h, dates, dates[-1], "ALL", "foreign", "A"), {"days": 2, "atLeast": False})

    def test_missing_session_is_not_skipped(self):
        dates = ["2026-11-05", "2026-11-06", "2026-11-09"]
        h = {dates[0]: entry(["A"]), dates[2]: entry(["A"])}
        self.assertEqual(streak(h, dates, dates[-1], "ALL", "foreign", "A"), {"days": 1, "atLeast": True})

    def test_same_day_replacement_does_not_add_days(self):
        dates = ["2026-11-06"]
        h = {dates[0]: entry(["A"])}
        h[dates[0]] = entry(["A"])
        self.assertEqual(streak(h, dates, dates[0], "ALL", "foreign", "A")["days"], 1)

if __name__ == "__main__":
    unittest.main()
