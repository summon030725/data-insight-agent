"""Make one tiny request to verify API authentication, model access, and quota."""

import os

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from data_agent import DEFAULT_MODEL, describe_openai_error


def main() -> int:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("未找到 OPENAI_API_KEY。")
        return 1

    try:
        OpenAI(timeout=30).responses.create(
            model=DEFAULT_MODEL,
            input="Reply with exactly: OK",
            max_output_tokens=32,
        )
    except OpenAIError as error:
        print(describe_openai_error(error, "API 诊断失败"))
        return 1

    print(f"API 诊断成功：认证、额度和模型 {DEFAULT_MODEL} 均可用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
