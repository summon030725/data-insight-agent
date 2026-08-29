"""Tests for agent construction that do not spend API credits."""

import unittest
from pathlib import Path
from types import SimpleNamespace

from data_agent import (
    DEFAULT_MODEL,
    MAX_QUESTION_LENGTH,
    DataAgentOutput,
    create_data_agent,
    load_sales,
    run_data_agent,
)
from data_agent.agent import _build_agent_input, _extract_tool_steps


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DataAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = create_data_agent(load_sales(PROJECT_ROOT / "data" / "sales.csv"))

    def test_agent_uses_low_cost_model(self) -> None:
        self.assertEqual(self.agent.model, DEFAULT_MODEL)

    def test_agent_has_eight_analysis_tools(self) -> None:
        tool_names = {tool.name for tool in self.agent.tools}
        self.assertEqual(
            tool_names,
            {
                "get_sales_summary",
                "get_profit_by_product",
                "get_profit_by_month",
                "get_performance_by_region",
                "get_refund_risks",
                "get_business_insights",
                "get_channel_and_segment_performance",
                "search_business_knowledge",
            },
        )

    def test_agent_uses_structured_output(self) -> None:
        self.assertIs(self.agent.output_type, DataAgentOutput)

    def test_tool_call_and_output_are_paired(self) -> None:
        items = [
            SimpleNamespace(
                type="tool_call_item",
                call_id="call_1",
                tool_name="get_profit_by_month",
                raw_item=SimpleNamespace(arguments="{}"),
            ),
            SimpleNamespace(
                type="tool_call_output_item",
                call_id="call_1",
                output='{"2026-04": 1657.0}',
            ),
        ]

        steps = _extract_tool_steps(items)

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].tool_name, "get_profit_by_month")
        self.assertEqual(steps[0].arguments, {})
        self.assertEqual(steps[0].output, {"2026-04": 1657.0})

    def test_new_question_is_appended_without_changing_history(self) -> None:
        history = [{"role": "user", "content": "哪个产品利润最高？"}]

        agent_input = _build_agent_input("它和第二名差多少？", history)

        self.assertEqual(len(history), 1)
        self.assertEqual(len(agent_input), 2)
        self.assertEqual(agent_input[-1]["content"], "它和第二名差多少？")

    def test_question_length_is_checked_before_api_call(self) -> None:
        import asyncio

        sales = load_sales(PROJECT_ROOT / "data" / "sales.csv")
        with self.assertRaisesRegex(ValueError, "问题不能超过"):
            asyncio.run(run_data_agent(sales, "问" * (MAX_QUESTION_LENGTH + 1)))


if __name__ == "__main__":
    unittest.main()
