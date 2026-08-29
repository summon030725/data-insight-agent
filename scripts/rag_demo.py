"""Run one semantic search against the local business knowledge index."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from data_agent import retrieve_business_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("没有找到 OPENAI_API_KEY，请检查项目根目录的 .env 文件。")

    question = "退款超过 3000 元时，需要经过哪些复核？"
    print(f"问题：{question}")
    for index, hit in enumerate(retrieve_business_knowledge(question), start=1):
        print(f"{index}. {hit.citation} score={hit.score:.4f}")
        print(f"   {hit.content}")


if __name__ == "__main__":
    main()
