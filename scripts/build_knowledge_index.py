"""Build the embedding index for the synthetic Markdown knowledge base."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from data_agent.rag import DEFAULT_INDEX_PATH, build_knowledge_index


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("没有找到 OPENAI_API_KEY，请检查项目根目录的 .env 文件。")

    index = build_knowledge_index()
    print(f"Embedding 模型：{index.embedding_model}")
    print(f"知识块数量：{len(index.chunks)}")
    print(f"索引文件：{DEFAULT_INDEX_PATH}")


if __name__ == "__main__":
    main()
