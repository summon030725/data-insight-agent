"""Two-agent workflow: plan analysis, collect evidence, then write a report."""

import json
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd
from agents import Agent, Runner
from pydantic import BaseModel, Field, field_validator

from .agent import DEFAULT_MODEL
from .analysis import summarize_sales
from .insights import (
    find_risk_orders,
    generate_business_insights,
    monthly_performance,
    performance_by_dimension,
)


AnalysisSection = Literal[
    "overview",
    "trend",
    "product",
    "region",
    "channel",
    "segment",
    "risk",
]


class AnalysisPlan(BaseModel):
    """Structured route selected by the planning agent."""

    request_summary: str = Field(description="用户分析目标的简洁中文概括")
    sections: list[AnalysisSection] = Field(
        min_length=2,
        max_length=6,
        description="为完成目标需要收集证据的分析模块，overview 必须包含",
    )
    rationale: str = Field(description="为什么这些模块足以回答当前问题")

    @field_validator("sections")
    @classmethod
    def keep_unique_sections(cls, sections: list[AnalysisSection]) -> list[AnalysisSection]:
        return list(dict.fromkeys(sections))


class ReportFinding(BaseModel):
    """One finding grounded in collected numerical evidence."""

    title: str
    evidence: str = Field(description="包含具体数字或维度名称的数据依据")
    interpretation: str = Field(description="谨慎解释该数据说明了什么，不声称因果")
    next_step: str = Field(description="用户可以继续核查的具体动作")


class AnalysisReport(BaseModel):
    """Structured report returned by the report-writing agent."""

    title: str
    executive_summary: str
    findings: list[ReportFinding]
    risk_alerts: list[str]
    recommended_actions: list[str]
    limitations: list[str]


@dataclass(frozen=True)
class AnalysisWorkflowRun:
    """User-visible trace across planning, evidence collection, and writing."""

    plan: AnalysisPlan
    evidence: dict[str, Any]
    report: AnalysisReport


def available_analysis_sections(frame: pd.DataFrame) -> list[AnalysisSection]:
    """List evidence modules supported by the current uploaded schema."""
    sections: list[AnalysisSection] = [
        "overview",
        "trend",
        "product",
        "region",
        "risk",
    ]
    if "channel" in frame.columns:
        sections.append("channel")
    if "customer_segment" in frame.columns:
        sections.append("segment")
    return sections


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-compatible records, including null values."""
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def collect_analysis_evidence(
    frame: pd.DataFrame,
    sections: list[AnalysisSection],
) -> dict[str, Any]:
    """Execute deterministic analysis modules selected by the planner."""
    if frame.empty:
        raise ValueError("数据为空，无法执行报告工作流。")

    evidence: dict[str, Any] = {}
    for section in sections:
        if section == "overview":
            evidence[section] = summarize_sales(frame)
        elif section == "trend":
            evidence[section] = _records(monthly_performance(frame))
        elif section == "product":
            evidence[section] = _records(performance_by_dimension(frame, "product"))
        elif section == "region":
            evidence[section] = _records(performance_by_dimension(frame, "region"))
        elif section == "channel" and "channel" in frame.columns:
            evidence[section] = _records(performance_by_dimension(frame, "channel"))
        elif section == "segment" and "customer_segment" in frame.columns:
            evidence[section] = _records(
                performance_by_dimension(frame, "customer_segment")
            )
        elif section == "risk":
            all_risks = find_risk_orders(frame)
            evidence[section] = {
                "total_risk_orders": len(all_risks),
                "loss_order_count": int((all_risks["profit"] < 0).sum()),
                "top_risk_orders": _records(all_risks.head(15)),
            }

    evidence["deterministic_insights"] = generate_business_insights(frame)
    return evidence


def create_analysis_planner() -> Agent:
    """Create an agent that selects a bounded set of evidence modules."""
    return Agent(
        name="分析规划 Agent",
        model=DEFAULT_MODEL,
        output_type=AnalysisPlan,
        instructions=(
            "你负责规划销售数据分析，不直接回答业务结论。"
            "根据用户目标从可用模块中选择2到6个模块，必须包含overview。"
            "只选择解决问题必要的模块，不能选择输入中未列出的模块。"
            "如果用户要求预测或因果分析，改为规划描述性证据与风险核查，并在理由中说明限制。"
        ),
    )


def create_report_writer() -> Agent:
    """Create an agent that turns collected evidence into a structured report."""
    return Agent(
        name="报告撰写 Agent",
        model=DEFAULT_MODEL,
        output_type=AnalysisReport,
        instructions=(
            "你是一名严谨的经营分析报告撰写者。"
            "只能使用输入中的plan和evidence，不得补充或重新计算不存在的数据。"
            "每个重要结论必须在evidence字段引用具体数字和维度名称。"
            "interpretation只能描述数据关系，不得把相关性写成因果。"
            "recommended_actions必须是可执行的核查或分析动作，不预测未来。"
            "limitations必须说明样本、字段或因果解释方面的重要限制。"
            "使用清晰简洁的中文。"
        ),
    )


async def run_analysis_workflow(
    frame: pd.DataFrame,
    request: str,
) -> AnalysisWorkflowRun:
    """Run planner, deterministic evidence collection, and report writer."""
    clean_request = request.strip()
    if not clean_request:
        raise ValueError("报告目标不能为空。")
    if len(clean_request) > 500:
        raise ValueError("报告目标不能超过 500 个字符。")

    available_sections = available_analysis_sections(frame)
    planner_input = json.dumps(
        {
            "user_request": clean_request,
            "available_sections": available_sections,
        },
        ensure_ascii=False,
    )
    plan_result = await Runner.run(
        create_analysis_planner(),
        planner_input,
        max_turns=2,
    )
    plan = plan_result.final_output
    if not isinstance(plan, AnalysisPlan):
        plan = AnalysisPlan.model_validate(plan)

    valid_sections = [
        section for section in plan.sections if section in available_sections
    ]
    if "overview" not in valid_sections:
        valid_sections.insert(0, "overview")
    if len(valid_sections) < 2:
        valid_sections.append("trend")
    plan = plan.model_copy(update={"sections": list(dict.fromkeys(valid_sections))})

    evidence = collect_analysis_evidence(frame, plan.sections)
    writer_input = json.dumps(
        {"plan": plan.model_dump(), "evidence": evidence},
        ensure_ascii=False,
    )
    report_result = await Runner.run(
        create_report_writer(),
        writer_input,
        max_turns=2,
    )
    report = report_result.final_output
    if not isinstance(report, AnalysisReport):
        report = AnalysisReport.model_validate(report)

    return AnalysisWorkflowRun(plan=plan, evidence=evidence, report=report)


def analysis_report_to_markdown(run: AnalysisWorkflowRun) -> str:
    """Convert the structured workflow result into a downloadable report."""
    report = run.report
    lines = [
        f"# {report.title}",
        "",
        report.executive_summary,
        "",
        "## 分析计划",
        "",
        f"- 目标：{run.plan.request_summary}",
        f"- 模块：{', '.join(run.plan.sections)}",
        f"- 理由：{run.plan.rationale}",
        "",
        "## 主要发现",
        "",
    ]
    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.title}",
                "",
                f"- 数据依据：{finding.evidence}",
                f"- 解读：{finding.interpretation}",
                f"- 下一步：{finding.next_step}",
                "",
            ]
        )
    lines.extend(["## 风险提示", ""])
    lines.extend(f"- {alert}" for alert in report.risk_alerts)
    lines.extend(["", "## 建议动作", ""])
    lines.extend(f"- {action}" for action in report.recommended_actions)
    lines.extend(["", "## 分析限制", ""])
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    return "\n".join(lines)
