"""Tests for safe OpenAI API error classification."""

import unittest

from data_agent.api_errors import describe_openai_error


class FakeAPIError(Exception):
    def __init__(
        self,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.request_id = request_id


class APIErrorMessageTests(unittest.TestCase):
    def test_authentication_error_has_actionable_message(self) -> None:
        message = describe_openai_error(FakeAPIError(status_code=401))

        self.assertIn("API Key 无效", message)
        self.assertIn("Streamlit Cloud", message)

    def test_project_spend_limit_is_distinguished(self) -> None:
        message = describe_openai_error(
            FakeAPIError(
                status_code=429,
                code="project_spend_limit_exceeded",
                request_id="req_test",
            )
        )

        self.assertIn("Project 已达到消费上限", message)
        self.assertIn("req_test", message)

    def test_server_error_is_retryable(self) -> None:
        message = describe_openai_error(FakeAPIError(status_code=503))

        self.assertIn("稍后重试", message)


if __name__ == "__main__":
    unittest.main()
