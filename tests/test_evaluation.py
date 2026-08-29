"""Offline tests for deterministic agent evaluation rules."""

import unittest

from data_agent.agent import AgentToolStep, DataAgentRun
from data_agent.evaluation import EvaluationCase, score_evaluation_case


def make_run(
    *,
    answer: str,
    status: str = "answered",
    tools: tuple[str, ...] = (),
) -> DataAgentRun:
    return DataAgentRun(
        answer=answer,
        status=status,
        missing_capability=None,
        tool_steps=tuple(
            AgentToolStep(tool_name=tool, arguments={}, output={}) for tool in tools
        ),
        history=[],
    )


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = EvaluationCase(
            id="summary",
            question="总利润是多少？",
            expected_status="answered",
            expected_tools=["get_sales_summary"],
            required_answer_terms=["5168"],
        )

    def test_matching_behavior_passes(self) -> None:
        result = score_evaluation_case(
            self.case,
            make_run(
                answer="总利润是 5,168 元。",
                tools=("get_sales_summary",),
            ),
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.issues, [])

    def test_wrong_tool_fails(self) -> None:
        result = score_evaluation_case(
            self.case,
            make_run(
                answer="总利润是 5,168 元。",
                tools=("get_profit_by_month",),
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("工具错误", result.issues[0])

    def test_missing_fact_fails(self) -> None:
        result = score_evaluation_case(
            self.case,
            make_run(
                answer="总利润表现良好。",
                tools=("get_sales_summary",),
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("答案缺少关键内容", result.issues[0])


if __name__ == "__main__":
    unittest.main()
