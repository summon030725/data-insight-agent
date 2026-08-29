"""Run the small live API evaluation suite and save a JSON report."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from data_agent import load_sales
from data_agent.evaluation import evaluate_cases, load_evaluation_cases


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("没有找到 OPENAI_API_KEY，请检查项目根目录的 .env 文件。")

    sales = load_sales(PROJECT_ROOT / "data" / "sales.csv")
    cases = load_evaluation_cases(PROJECT_ROOT / "evals" / "cases.json")
    report = await evaluate_cases(sales, cases)

    report_path = PROJECT_ROOT / "outputs" / "evaluation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    for result in report.results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"[{marker}] {result.id}: {result.question}")
        print(f"  status={result.actual_status}, tools={result.actual_tools}")
        if result.issues:
            print(f"  issues={result.issues}")

    print(
        f"\n总分：{report.passed_count}/{report.total_count} "
        f"({report.pass_rate:.0%})"
    )
    print(f"报告：{report_path}")


if __name__ == "__main__":
    asyncio.run(main())
