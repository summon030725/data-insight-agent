"""Deterministic business-analysis views used by both the UI and the agent."""

from typing import Literal

import pandas as pd


Dimension = Literal["product", "region", "channel", "customer_segment"]
SUPPORTED_DIMENSIONS = {"product", "region", "channel", "customer_segment"}


def _safe_percentage(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Calculate percentages while keeping zero-revenue groups stable."""
    return numerator.div(denominator.where(denominator.ne(0))).fillna(0).mul(100)


def performance_by_dimension(
    frame: pd.DataFrame,
    dimension: Dimension,
) -> pd.DataFrame:
    """Return orders, revenue, profit, margin, and refunds by one dimension."""
    if dimension not in SUPPORTED_DIMENSIONS:
        raise ValueError(f"不支持的分析维度：{dimension}")
    if dimension not in frame.columns:
        raise ValueError(f"数据缺少分析字段：{dimension}")
    if frame.empty:
        raise ValueError("数据为空，无法进行维度分析。")

    grouped = (
        frame.groupby(dimension, as_index=False)
        .agg(
            order_count=("order_id", "nunique"),
            quantity=("quantity", "sum"),
            revenue=("revenue", "sum"),
            profit=("profit", "sum"),
            refund_amount=("refund_amount", "sum"),
        )
        .sort_values("profit", ascending=False)
        .reset_index(drop=True)
    )
    grouped["profit_margin"] = _safe_percentage(
        grouped["profit"], grouped["revenue"]
    ).round(2)
    grouped["refund_rate"] = _safe_percentage(
        grouped["refund_amount"], grouped["revenue"]
    ).round(2)
    return grouped


def monthly_performance(frame: pd.DataFrame) -> pd.DataFrame:
    """Return monthly KPIs and month-over-month profit growth."""
    if frame.empty:
        raise ValueError("数据为空，无法进行月度分析。")

    monthly_frame = frame.assign(month=frame["date"].dt.strftime("%Y-%m"))
    grouped = (
        monthly_frame.groupby("month", as_index=False)
        .agg(
            order_count=("order_id", "nunique"),
            revenue=("revenue", "sum"),
            profit=("profit", "sum"),
            refund_amount=("refund_amount", "sum"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    grouped["profit_margin"] = _safe_percentage(
        grouped["profit"], grouped["revenue"]
    ).round(2)
    grouped["profit_growth"] = grouped["profit"].pct_change().mul(100).round(2)
    return grouped


def find_risk_orders(
    frame: pd.DataFrame,
    limit: int | None = None,
) -> pd.DataFrame:
    """Find refunded or loss-making orders and explain why they need attention."""
    if frame.empty:
        return frame.copy()

    detail_columns = [
        "order_id",
        "date",
        "region",
        "product",
        *(
            [column]
            if (column := "channel") in frame.columns
            else []
        ),
        "revenue",
        "refund_amount",
        "profit",
    ]
    risks = frame.loc[
        (frame["refund_amount"] > 0) | (frame["profit"] < 0),
        detail_columns,
    ].copy()
    risks["risk_reason"] = risks.apply(
        lambda row: (
            "亏损且发生退款"
            if row["profit"] < 0 and row["refund_amount"] > 0
            else "订单亏损"
            if row["profit"] < 0
            else "发生退款"
        ),
        axis=1,
    )
    sorted_risks = risks.sort_values(
        ["profit", "refund_amount"], ascending=[True, False]
    ).reset_index(drop=True)
    return sorted_risks.head(limit) if limit is not None else sorted_risks


def generate_business_insights(frame: pd.DataFrame) -> list[dict[str, str]]:
    """Generate evidence-backed findings and cautious next-step suggestions."""
    if frame.empty:
        return []

    product = performance_by_dimension(frame, "product")
    region = performance_by_dimension(frame, "region")
    monthly = monthly_performance(frame)
    risks = find_risk_orders(frame)
    insights: list[dict[str, str]] = []

    top_product = product.iloc[0]
    total_profit = frame["profit"].sum()
    profit_share = top_product["profit"] / total_profit * 100 if total_profit else 0
    insights.append(
        {
            "level": "positive",
            "title": f"{top_product['product']} 是利润贡献最高的产品",
            "finding": (
                f"贡献利润 {top_product['profit']:,.0f}，占筛选范围总利润的 "
                f"{profit_share:.1f}%。"
            ),
            "action": "建议继续观察销量与利润率是否同步，避免只依赖单一指标。",
        }
    )

    weakest_region = region.sort_values("profit_margin").iloc[0]
    insights.append(
        {
            "level": "warning" if weakest_region["refund_rate"] > 0 else "info",
            "title": f"{weakest_region['region']} 区域利润率最低",
            "finding": (
                f"利润率 {weakest_region['profit_margin']:.1f}%，退款率 "
                f"{weakest_region['refund_rate']:.1f}%。"
            ),
            "action": "建议检查该区域的退款订单、产品组合和定价差异。",
        }
    )

    if len(monthly) >= 2:
        latest = monthly.iloc[-1]
        previous = monthly.iloc[-2]
        growth = latest["profit_growth"]
        direction = "回升" if growth >= 0 else "下降"
        insights.append(
            {
                "level": "positive" if growth >= 0 else "warning",
                "title": f"最近一个月利润{direction}",
                "finding": (
                    f"{latest['month']} 利润 {latest['profit']:,.0f}，较 "
                    f"{previous['month']} 变化 {growth:+.1f}%。"
                ),
                "action": "建议结合产品和地区拆分，确认变化来自哪些业务单元。",
            }
        )

    if "channel" in frame.columns:
        channels = performance_by_dimension(frame, "channel")
        top_channel = channels.iloc[0]
        insights.append(
            {
                "level": "info",
                "title": f"{top_channel['channel']} 渠道利润贡献最高",
                "finding": (
                    f"利润 {top_channel['profit']:,.0f}，利润率 "
                    f"{top_channel['profit_margin']:.1f}%。"
                ),
                "action": "建议结合客群与产品拆分，判断渠道优势是否稳定。",
            }
        )

    if not risks.empty:
        loss_count = int((risks["profit"] < 0).sum())
        insights.append(
            {
                "level": "warning",
                "title": f"发现 {len(risks)} 笔退款或亏损风险订单",
                "finding": (
                    f"其中 {loss_count} 笔订单利润为负，退款金额合计 "
                    f"{risks['refund_amount'].sum():,.0f}。"
                ),
                "action": "建议优先复核风险订单明细，确认退款原因和成本记录。",
            }
        )

    return insights


def build_analysis_report(frame: pd.DataFrame) -> str:
    """Build a downloadable Markdown snapshot from the current filtered data."""
    if frame.empty:
        raise ValueError("数据为空，无法生成分析报告。")

    total_revenue = float(frame["revenue"].sum())
    total_profit = float(frame["profit"].sum())
    total_refunds = float(frame["refund_amount"].sum())
    margin = total_profit / total_revenue * 100 if total_revenue else 0
    lines = [
        "# 销售数据分析快照",
        "",
        "## 核心指标",
        "",
        f"- 订单数：{frame['order_id'].nunique()}",
        f"- 销售额：{total_revenue:,.2f}",
        f"- 利润：{total_profit:,.2f}",
        f"- 利润率：{margin:.2f}%",
        f"- 退款金额：{total_refunds:,.2f}",
        "",
        "## 自动洞察与建议",
        "",
    ]
    for insight in generate_business_insights(frame):
        lines.extend(
            [
                f"### {insight['title']}",
                "",
                insight["finding"],
                "",
                f"下一步：{insight['action']}",
                "",
            ]
        )
    lines.append(
        "> 注意：以上建议基于描述性统计，不代表因果结论或未来预测。"
    )
    return "\n".join(lines)
