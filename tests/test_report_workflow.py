"""Offline tests for the planned analysis report workflow."""

import unittest
from pathlib import Path

from data_agent import (
    AnalysisPlan,
    AnalysisReport,
    AnalysisWorkflowRun,
    ReportFinding,
    analysis_report_to_markdown,
    available_analysis_sections,
    collect_analysis_evidence,
    load_sales,
)


class ReportWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.sales = load_sales(project_root / "data" / "sales_large.csv")

    def test_available_sections_follow_schema(self) -> None:
        sections = available_analysis_sections(self.sales)

        self.assertIn("channel", sections)
        self.assertIn("segment", sections)
        self.assertIn("risk", sections)

    def test_evidence_collection_runs_only_selected_modules(self) -> None:
        evidence = collect_analysis_evidence(
            self.sales,
            ["overview", "channel", "risk"],
        )

        self.assertIn("overview", evidence)
        self.assertIn("channel", evidence)
        self.assertNotIn("trend", evidence)
        self.assertGreater(evidence["risk"]["total_risk_orders"], 0)
        self.assertLessEqual(len(evidence["risk"]["top_risk_orders"]), 15)

    def test_report_markdown_preserves_plan_and_evidence(self) -> None:
        plan = AnalysisPlan(
            request_summary="定位利润和退款风险",
            sections=["overview", "risk"],
            rationale="需要总体指标和订单风险证据。",
        )
        report = AnalysisReport(
            title="经营风险报告",
            executive_summary="当前存在需要复核的退款订单。",
            findings=[
                ReportFinding(
                    title="风险订单",
                    evidence="风险订单 10 笔。",
                    interpretation="风险集中需要进一步核查。",
                    next_step="复核退款原因。",
                )
            ],
            risk_alerts=["不要把退款相关性解释为原因。"],
            recommended_actions=["检查退款记录。"],
            limitations=["数据不包含退款原因。"],
        )
        markdown = analysis_report_to_markdown(
            AnalysisWorkflowRun(plan=plan, evidence={}, report=report)
        )

        self.assertIn("overview, risk", markdown)
        self.assertIn("风险订单 10 笔", markdown)
        self.assertIn("数据不包含退款原因", markdown)


if __name__ == "__main__":
    unittest.main()
