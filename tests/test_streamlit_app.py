"""Smoke test for the Streamlit interface."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_app_loads_sample_data_without_errors(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app = AppTest.from_file(project_root / "streamlit_app.py").run(timeout=15)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.title[0].value, "智能数据分析 Agent")
        self.assertGreaterEqual(len(app.metric), 5)
        self.assertEqual(app.text_input[0].label, "你想了解什么？")
        self.assertEqual(app.button[0].label, "让 Agent 分析")
        self.assertEqual(app.button[1].label, "清空对话")
        self.assertEqual(app.text_area[0].label, "这份报告要重点解决什么问题？")
        self.assertEqual(app.text_input[1].label, "检索业务知识库")
        self.assertEqual(app.button[2].label, "检索知识库")
        self.assertEqual(app.button[3].label, "生成深度报告")

    def test_empty_question_does_not_call_api(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app = AppTest.from_file(project_root / "streamlit_app.py").run(timeout=15)

        app.button[0].click().run(timeout=15)

        self.assertEqual(len(app.exception), 0)
        self.assertIn("请先输入一个问题。", [warning.value for warning in app.warning])


if __name__ == "__main__":
    unittest.main()
