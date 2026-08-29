"""Run one sample question through the sales data agent."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from data_agent import ask_data_agent, load_sales


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("没有找到 OPENAI_API_KEY，请检查项目根目录的 .env 文件。")

    sales = load_sales(PROJECT_ROOT / "data" / "sales.csv")
    question = "哪个产品利润最高？请说明依据。"
    print(f"问题：{question}")
    print("Agent：", await ask_data_agent(sales, question))


if __name__ == "__main__":
    asyncio.run(main())
