"""Tests for the deterministic portfolio-sized sample dataset."""

import unittest
from pathlib import Path

from data_agent import load_sales


class LargeSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.sales = load_sales(project_root / "data" / "sales_large.csv")

    def test_large_sample_has_expected_scale_and_dimensions(self) -> None:
        self.assertEqual(len(self.sales), 1_500)
        self.assertTrue(
            {"channel", "customer_segment", "customer_id"}.issubset(
                self.sales.columns
            )
        )
        self.assertEqual(self.sales["product"].nunique(), 8)
        self.assertEqual(self.sales["region"].nunique(), 5)

    def test_large_sample_contains_realistic_risk_cases(self) -> None:
        self.assertGreater((self.sales["refund_amount"] > 0).sum(), 50)
        self.assertGreater((self.sales["profit"] < 0).sum(), 20)


if __name__ == "__main__":
    unittest.main()
