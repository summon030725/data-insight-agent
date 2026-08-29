"""Tests for deterministic data analysis tools."""

import unittest
from pathlib import Path

from data_agent import load_sales, profit_by_month, profit_by_product, summarize_sales


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.sales = load_sales(project_root / "data" / "sales.csv")

    def test_calculated_columns_are_added(self) -> None:
        self.assertIn("revenue", self.sales.columns)
        self.assertIn("profit", self.sales.columns)

    def test_first_order_profit(self) -> None:
        self.assertEqual(self.sales.iloc[0]["profit"], 357)

    def test_summary(self) -> None:
        summary = summarize_sales(self.sales)
        self.assertEqual(summary["order_count"], 12)
        self.assertEqual(summary["top_product_by_profit"], "Keyboard")

    def test_profit_by_product(self) -> None:
        result = profit_by_product(self.sales)

        self.assertEqual(result["Keyboard"], 1843.0)
        self.assertEqual(result["Monitor"], 1813.0)
        self.assertEqual(result["Mouse"], 1512.0)

    def test_profit_by_month(self) -> None:
        result = profit_by_month(self.sales)

        self.assertEqual(result["2026-01"], 1430.0)
        self.assertEqual(result["2026-02"], 1208.0)
        self.assertEqual(result["2026-03"], 873.0)
        self.assertEqual(result["2026-04"], 1657.0)


if __name__ == "__main__":
    unittest.main()
