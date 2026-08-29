"""Small, repeatable evaluation suite for the sales data agent."""

import re
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, TypeAdapter

from .agent import DEFAULT_MODEL, DataAgentRun, run_data_agent


class EvaluationCase(BaseModel):
    """One question and the observable behavior expected from the agent."""

    id: str
    question: str
    expected_status: Literal["answered", "unsupported"]
    expected_tools: list[str]
    required_answer_terms: list[str]


class EvaluationResult(BaseModel):
    """Machine-readable score and evidence for one evaluation case."""

    id: str
    question: str
    passed: bool
    expected_status: str
    actual_status: str
    expected_tools: list[str]
    actual_tools: list[str]
    required_answer_terms: list[str]
    answer: str
    issues: list[str]


class EvaluationReport(BaseModel):
    """Aggregate results for one complete evaluation run."""

    model: str
    passed_count: int
    total_count: int
    pass_rate: float
    results: list[EvaluationResult]


def load_evaluation_cases(path: str | Path) -> list[EvaluationCase]:
    """Load and validate evaluation cases from JSON."""
    content = Path(path).read_text(encoding="utf-8")
    return TypeAdapter(list[EvaluationCase]).validate_json(content)


def _normalize(text: str) -> str:
    """Ignore harmless whitespace and thousands separators when scoring terms."""
    return re.sub(r"[\s,，]", "", text.casefold())


def score_evaluation_case(
    case: EvaluationCase,
    run: DataAgentRun,
) -> EvaluationResult:
    """Score status, chosen tools, and required facts without another LLM call."""
    actual_tools = [step.tool_name for step in run.tool_steps]
    issues: list[str] = []

    if run.status != case.expected_status:
        issues.append(
            f"状态错误：期望 {case.expected_status}，实际 {run.status}"
        )

    if set(actual_tools) != set(case.expected_tools):
        issues.append(
            f"工具错误：期望 {case.expected_tools}，实际 {actual_tools}"
        )

    normalized_answer = _normalize(run.answer)
    missing_terms = [
        term
        for term in case.required_answer_terms
        if _normalize(term) not in normalized_answer
    ]
    if missing_terms:
        issues.append(f"答案缺少关键内容：{missing_terms}")

    return EvaluationResult(
        id=case.id,
        question=case.question,
        passed=not issues,
        expected_status=case.expected_status,
        actual_status=run.status,
        expected_tools=case.expected_tools,
        actual_tools=actual_tools,
        required_answer_terms=case.required_answer_terms,
        answer=run.answer,
        issues=issues,
    )


async def evaluate_cases(
    sales: pd.DataFrame,
    cases: list[EvaluationCase],
) -> EvaluationReport:
    """Run cases sequentially and return a regression-friendly report."""
    if not cases:
        raise ValueError("评测用例不能为空。")

    results: list[EvaluationResult] = []
    for case in cases:
        run = await run_data_agent(sales, case.question)
        results.append(score_evaluation_case(case, run))

    passed_count = sum(result.passed for result in results)
    return EvaluationReport(
        model=DEFAULT_MODEL,
        passed_count=passed_count,
        total_count=len(results),
        pass_rate=passed_count / len(results),
        results=results,
    )
