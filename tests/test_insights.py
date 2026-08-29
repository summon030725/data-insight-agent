"""Tests for deeper deterministic analysis and report generation."""

import unittest
from pathlib import Path

from data_agent import (
    build_analysis_report,
    find_risk_orders,
    generate_business_insights,
    load_sales,
    monthly_performance,
    performance_by_dimension,
)


class InsightsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.sales = load_sales(project_root / "data" / "sales.csv")

    def test_region_performance_contains_margin_and_refund_rate(self) -> None:
        regions = performance_by_dimension(self.sales, "region")

        self.assertEqual(regions.iloc[0]["region"], "West")
        self.assertEqual(regions.iloc[0]["profit"], 1844)
        self.assertIn("profit_margin", regions.columns)
        self.assertIn("refund_rate", regions.columns)

    def test_monthly_performance_calculates_growth(self) -> None:
        monthly = monthly_performance(self.sales)

        self.assertEqual(monthly.iloc[-1]["month"], "2026-04")
        self.assertAlmostEqual(monthly.iloc[-1]["profit_growth"], 89.81)

    def test_risk_orders_put_loss_order_first(self) -> None:
        risks = find_risk_orders(self.sales)

        self.assertEqual(risks.iloc[0]["order_id"], 1009)
        self.assertEqual(risks.iloc[0]["risk_reason"], "亏损且发生退款")

    def test_risk_order_limit_is_respected(self) -> None:
        risks = find_risk_orders(self.sales, limit=2)

        self.assertEqual(len(risks), 2)

    def test_insights_include_actions(self) -> None:
        insights = generate_business_insights(self.sales)

        self.assertGreaterEqual(len(insights), 4)
        self.assertTrue(all(insight["action"] for insight in insights))

    def test_markdown_report_contains_caveat(self) -> None:
        report = build_analysis_report(self.sales)

        self.assertIn("自动洞察与建议", report)
        self.assertIn("不代表因果结论或未来预测", report)


if __name__ == "__main__":
    unittest.main()
