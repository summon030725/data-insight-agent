"""Run the two-agent report workflow against the large sample dataset."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from data_agent import load_sales, run_analysis_workflow


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("没有找到 OPENAI_API_KEY，请检查项目根目录的 .env 文件。")

    sales = load_sales(PROJECT_ROOT / "data" / "sales_large.csv")
    workflow = await run_analysis_workflow(
        sales,
        "分析整体经营表现，定位利润、渠道和退款风险，并给出下一步核查建议。",
    )
    output_path = PROJECT_ROOT / "outputs" / "agent_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        workflow.report.model_dump_json(indent=2), encoding="utf-8"
    )
    print(f"计划模块：{workflow.plan.sections}")
    print(f"报告标题：{workflow.report.title}")
    print(f"主要发现：{len(workflow.report.findings)} 条")
    print(f"报告文件：{output_path}")


if __name__ == "__main__":
    asyncio.run(main())
