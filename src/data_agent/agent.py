"""LLM agent that answers questions by calling deterministic data tools."""

import json
from dataclasses import dataclass
from typing import Any, Iterable, Literal

import pandas as pd
from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field

from .analysis import profit_by_month, profit_by_product, summarize_sales
from .insights import (
    find_risk_orders,
    generate_business_insights,
    performance_by_dimension,
)
from .rag import retrieve_business_knowledge


DEFAULT_MODEL = "gpt-5.6-luna"
MAX_QUESTION_LENGTH = 500


class DataAgentOutput(BaseModel):
    """Structured final output that makes capability boundaries explicit."""

    status: Literal["answered", "unsupported"] = Field(
        description="answered if reliable tools or conversation evidence support the answer; otherwise unsupported"
    )
    answer: str = Field(description="Concise Chinese response shown to the user")
    missing_capability: str | None = Field(
        description="Specific missing data or analysis tool when unsupported; null when answered"
    )


@dataclass(frozen=True)
class AgentToolStep:
    """One real tool call recorded during an agent run."""

    tool_name: str
    arguments: Any
    output: Any


@dataclass(frozen=True)
class DataAgentRun:
    """Final answer, tool records, and replay-ready conversation history."""

    answer: str
    status: Literal["answered", "unsupported"]
    missing_capability: str | None
    tool_steps: tuple[AgentToolStep, ...]
    history: list[Any]


def _decode_json(value: Any) -> Any:
    """Decode SDK JSON strings while preserving non-JSON values."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _extract_tool_steps(items: Iterable[Any]) -> tuple[AgentToolStep, ...]:
    """Pair tool-call items with their corresponding tool outputs."""
    calls: dict[str, dict[str, Any]] = {}
    call_order: list[str] = []

    for item in items:
        if item.type == "tool_call_item":
            call_id = item.call_id or f"tool_call_{len(call_order) + 1}"
            raw_arguments = getattr(item.raw_item, "arguments", "{}")
            calls[call_id] = {
                "tool_name": item.tool_name or "unknown_tool",
                "arguments": _decode_json(raw_arguments),
                "output": None,
            }
            call_order.append(call_id)
        elif item.type == "tool_call_output_item" and item.call_id in calls:
            calls[item.call_id]["output"] = _decode_json(item.output)

    return tuple(AgentToolStep(**calls[call_id]) for call_id in call_order)


def _build_agent_input(question: str, history: list[Any] | None = None) -> list[Any]:
    """Append a new user message without mutating the saved history."""
    return [
        *(history or []),
        {"role": "user", "content": question.strip()},
    ]


def create_data_agent(sales: pd.DataFrame) -> Agent:
    """Create an agent whose tools operate on the supplied sales data."""

    @function_tool
    def get_sales_summary() -> str:
        """获取订单数、总销售额、总利润和利润最高的产品。"""
        return json.dumps(summarize_sales(sales), ensure_ascii=False)

    @function_tool
    def get_profit_by_product() -> str:
        """获取每个产品的总利润，用于比较不同产品。"""
        return json.dumps(profit_by_product(sales), ensure_ascii=False)

    @function_tool
    def get_profit_by_month() -> str:
        """获取每个月的总利润，用于分析月度变化。"""
        return json.dumps(profit_by_month(sales), ensure_ascii=False)

    @function_tool
    def get_performance_by_region() -> str:
        """获取各地区的订单、销售额、利润、利润率和退款率，用于地区对比。"""
        records = performance_by_dimension(sales, "region").to_dict(orient="records")
        return json.dumps(records, ensure_ascii=False)

    @function_tool
    def get_refund_risks() -> str:
        """获取最需关注的20笔退款或亏损订单，避免返回过多明细。"""
        risks = find_risk_orders(sales, limit=20).copy()
        if "date" in risks:
            risks["date"] = risks["date"].dt.strftime("%Y-%m-%d")
        return json.dumps(risks.to_dict(orient="records"), ensure_ascii=False)

    @function_tool
    def get_business_insights() -> str:
        """获取基于当前数据的自动洞察和谨慎的下一步检查建议。"""
        return json.dumps(generate_business_insights(sales), ensure_ascii=False)

    @function_tool
    def get_channel_and_segment_performance() -> str:
        """获取渠道和客户类型的销售额、利润、利润率与退款率，用于经营结构对比。"""
        required_columns = {"channel", "customer_segment"}
        missing = required_columns - set(sales.columns)
        if missing:
            return json.dumps(
                {"unsupported": f"数据缺少字段：{', '.join(sorted(missing))}"},
                ensure_ascii=False,
            )
        result = {
            "channel": performance_by_dimension(sales, "channel").to_dict(
                orient="records"
            ),
            "customer_segment": performance_by_dimension(
                sales, "customer_segment"
            ).to_dict(orient="records"),
        }
        return json.dumps(result, ensure_ascii=False)

    @function_tool
    def search_business_knowledge(query: str) -> str:
        """检索退款政策、区域手册、渠道规则和产品售后指南；政策问题或规则依据必须使用。"""
        hits = retrieve_business_knowledge(query, top_k=4)
        return json.dumps(
            [hit.model_dump() for hit in hits], ensure_ascii=False
        )

    return Agent(
        name="销售数据分析助手",
        model=DEFAULT_MODEL,
        output_type=DataAgentOutput,
        instructions=(
            "你是一名严谨的销售数据分析助手。"
            "你可以回答订单数量、销售额、利润、利润率、产品和月度对比、地区表现、"
            "退款与亏损风险、渠道和客户类型，并能基于描述性统计提出下一步检查建议。"
            "能回答时先选择合适工具读取真实数据；也可以使用本对话中已有的工具结果回答追问。"
            "地区问题使用地区工具，具体退款或亏损订单使用风险工具，综合建议使用洞察工具。"
            "渠道或客户类型问题使用经营结构工具；如果工具返回 unsupported，必须说明缺少字段。"
            "政策、规则、操作手册或处理时限问题必须使用知识库检索工具。"
            "同时涉及经营数字和政策的问题，要分别调用数据工具与知识库工具后综合回答。"
            "引用知识库内容时必须保留工具返回的[source#section]格式来源。"
            "不能预测未来、断言因果关系或回答具体客户隐私问题。"
            "只能根据工具结果或对话中已有的工具证据作答，绝不计算或编造缺失数据。"
            "如果现有工具无法回答，要说明缺少的具体数据或分析工具，并建议下一步。"
            "回答使用简洁中文，并说明结论所依据的关键数字。"
        ),
        tools=[
            get_sales_summary,
            get_profit_by_product,
            get_profit_by_month,
            get_performance_by_region,
            get_refund_risks,
            get_business_insights,
            get_channel_and_segment_performance,
            search_business_knowledge,
        ],
    )


async def run_data_agent(
    sales: pd.DataFrame,
    question: str,
    history: list[Any] | None = None,
) -> DataAgentRun:
    """Run the agent and return both its answer and real tool-call records."""
    clean_question = question.strip()
    if not clean_question:
        raise ValueError("问题不能为空。")
    if len(clean_question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"问题不能超过 {MAX_QUESTION_LENGTH} 个字符。")

    result = await Runner.run(
        create_data_agent(sales),
        _build_agent_input(clean_question, history),
        max_turns=4,
    )
    output = result.final_output
    if not isinstance(output, DataAgentOutput):
        output = DataAgentOutput.model_validate(output)

    return DataAgentRun(
        answer=output.answer,
        status=output.status,
        missing_capability=output.missing_capability,
        tool_steps=_extract_tool_steps(result.new_items),
        history=result.to_input_list(),
    )


async def ask_data_agent(sales: pd.DataFrame, question: str) -> str:
    """Ask one question and return only the final answer."""
    return (await run_data_agent(sales, question)).answer
