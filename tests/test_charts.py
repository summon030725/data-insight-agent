"""Tests for chart generation helpers."""

import tempfile
import unittest
from pathlib import Path

from data_agent import save_monthly_profit_chart


class ChartTests(unittest.TestCase):
    def test_save_monthly_profit_chart(self) -> None:
        monthly_profits = {
            "2026-01": 1430.0,
            "2026-02": 1208.0,
            "2026-03": 873.0,
            "2026-04": 1657.0,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            chart_path = save_monthly_profit_chart(
                monthly_profits, Path(temporary_directory) / "monthly_profit.png"
            )

            self.assertTrue(chart_path.exists())
            self.assertGreater(chart_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
