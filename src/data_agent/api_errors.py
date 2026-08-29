"""Safe, actionable OpenAI API error messages for the public app."""

from typing import Any


def _error_code(error: Any) -> str | None:
    """Read an SDK error code without exposing the raw response message."""
    code = getattr(error, "code", None)
    if code:
        return str(code)

    body = getattr(error, "body", None)
    if isinstance(body, dict):
        nested = body.get("error")
        if isinstance(nested, dict) and nested.get("code"):
            return str(nested["code"])
        if body.get("code"):
            return str(body["code"])
    return None


def describe_openai_error(error: Any, operation: str = "OpenAI API") -> str:
    """Convert an SDK exception into a safe troubleshooting message."""
    status = getattr(error, "status_code", None)
    code = _error_code(error)
    error_name = type(error).__name__

    if status == 401:
        message = (
            "API Key 无效、已撤销，或不属于当前项目（HTTP 401）。"
            "请在 Streamlit Cloud 的 Secrets 中重新填写有效的项目 API Key。"
        )
    elif status == 403:
        message = (
            "当前 API Key 没有所请求模型的权限，或部署地区不受支持（HTTP 403）。"
        )
    elif status == 404:
        message = "当前项目无法访问所配置的模型（HTTP 404）。"
    elif status == 429:
        quota_messages = {
            "credit_balance_exhausted": "当前组织的预付额度已经用完。",
            "organization_spend_limit_exceeded": "当前组织已达到消费上限。",
            "project_spend_limit_exceeded": "当前 Project 已达到消费上限。",
            "organization_usage_limit_exceeded": "当前组织已达到平台分配的使用上限。",
        }
        message = quota_messages.get(
            code,
            "请求触发了速率限制或额度限制。请检查 Billing、Project Limits，稍后再试。",
        )
        message = f"{message}（HTTP 429{f'，{code}' if code else ''}）"
    elif status == 400:
        message = "API 请求参数或模型配置不兼容（HTTP 400）。"
    elif isinstance(status, int) and status >= 500:
        message = f"OpenAI 服务暂时异常（HTTP {status}），请稍后重试。"
    elif error_name == "APITimeoutError":
        message = "API 请求超时，请稍后重试。"
    elif error_name == "APIConnectionError":
        message = "服务器无法连接 OpenAI API，请检查部署平台的网络状态。"
    else:
        details = f"HTTP {status}" if status else error_name
        message = f"API 请求失败（{details}）。"

    request_id = getattr(error, "request_id", None)
    if request_id:
        message += f" 请求编号：{request_id}"
    return f"{operation}：{message}"
