"""Chart generation helpers for analysis results."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "data-analysis-agent-matplotlib")
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def save_monthly_profit_chart(
    monthly_profits: dict[str, float], output_path: str | Path
) -> Path:
    """Save monthly profit values as a line chart and return its path."""
    if not monthly_profits:
        raise ValueError("没有月度利润数据，无法生成图表。")

    chart_path = Path(output_path)
    chart_path.parent.mkdir(parents=True, exist_ok=True)

    months = list(monthly_profits.keys())
    profits = list(monthly_profits.values())

    figure, axes = plt.subplots(figsize=(8, 4.5))
    axes.plot(months, profits, marker="o", linewidth=2)
    axes.set_title("Monthly Profit")
    axes.set_xlabel("Month")
    axes.set_ylabel("Profit")
    axes.grid(axis="y", alpha=0.25)

    for month, profit in zip(months, profits, strict=True):
        axes.annotate(
            f"{profit:.0f}",
            (month, profit),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
        )

    figure.tight_layout()
    figure.savefig(chart_path, dpi=160)
    plt.close(figure)
    return chart_path
