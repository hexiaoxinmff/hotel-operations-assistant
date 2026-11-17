import csv
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("daily_metrics", Path(__file__).resolve().parents[1] / "scripts" / "check_daily_metrics.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class DailyMetricsTests(unittest.TestCase):
    def run_rows(self, rows, headers=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(headers or mod.REQUIRED)
                writer.writerows(rows)
            before = hashlib.sha256(path.read_bytes()).digest()
            result = mod.analyze(path)
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).digest())
            return result

    def row(self, available="3000", sold="2100", revenue="630000", day="2026-10-31", currency="CNY"):
        return ["001", day, currency, available, sold, revenue]

    def test_known_metrics(self):
        r = self.run_rows([self.row()])["rows"][0]
        self.assertEqual([r["metrics"][k]["value"] for k in ("occupancy_percent", "adr", "revpar")], ["70.00", "300.00", "210.00"])
        self.assertEqual(r["key"][0], "001")

    def test_zero_denominator(self):
        r = self.run_rows([self.row("0", "0", "0")])["rows"][0]
        self.assertTrue(all(x["value"] is None for x in r["metrics"].values()))

    def test_blank_not_zero(self):
        r = self.run_rows([self.row(revenue="")])["rows"][0]
        self.assertIn("INVALID_ROOM_REVENUE", r["errors"])
        self.assertIsNone(r["metrics"])

    def test_duplicates_all_flagged_not_deleted(self):
        r = self.run_rows([self.row(), self.row()])
        self.assertEqual(r["record_count"], 2)
        self.assertTrue(all("DUPLICATE_DAILY_KEY_REVIEW" in x["flags"] for x in r["rows"]))

    def test_currencies_not_merged(self):
        r = self.run_rows([self.row(), self.row(currency="USD")])
        self.assertEqual(r["review_records"], 0)
        self.assertNotIn("total_revenue", r)

    def test_sold_exceeds_inventory(self):
        r = self.run_rows([self.row("5", "6", "10")])["rows"][0]
        self.assertIn("SOLD_EXCEEDS_AVAILABLE", r["flags"])

    def test_negative_revenue_flagged(self):
        self.assertIn("NEGATIVE_REVENUE_REVIEW", self.run_rows([self.row(revenue="-1.25")])["rows"][0]["flags"])

    def test_invalid_amounts(self):
        for amount in ["NaN", "Infinity", "1,000", "1.001", "￥20"]:
            with self.subTest(amount=amount):
                self.assertIsNone(self.run_rows([self.row(revenue=amount)])["rows"][0]["metrics"])

    def test_invalid_calendar_date(self):
        self.assertIn("INVALID_BUSINESS_DATE", self.run_rows([self.row(day="2026-02-30")])["rows"][0]["errors"])

    def test_decimal_rounding(self):
        self.assertEqual(self.run_rows([self.row("3", "3", "10")])["rows"][0]["metrics"]["adr"]["value"], "3.33")

    def test_no_sold_but_revenue(self):
        r = self.run_rows([self.row("3", "0", "10")])["rows"][0]
        self.assertIn("REVENUE_WITHOUT_SOLD_ROOM_NIGHTS", r["flags"])
        self.assertIsNone(r["metrics"]["adr"]["value"])

    def test_missing_or_duplicate_headers(self):
        for headers in [list(mod.REQUIRED)[:-1], list(mod.REQUIRED) + [mod.REQUIRED[0]]]:
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.run_rows([], headers)

if __name__ == "__main__":
    unittest.main()
