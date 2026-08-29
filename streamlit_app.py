"""Interactive analysis cockpit for the sales data agent project."""

import asyncio
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from agents.exceptions import AgentsException, MaxTurnsExceeded, ModelBehaviorError
from dotenv import load_dotenv
from openai import OpenAIError

from data_agent import (
    EMBEDDING_MODEL,
    MAX_QUESTION_LENGTH,
    analysis_report_to_markdown,
    build_analysis_report,
    describe_openai_error,
    find_risk_orders,
    generate_business_insights,
    load_sales,
    load_knowledge_chunks,
    load_knowledge_index,
    monthly_performance,
    performance_by_dimension,
    run_data_agent,
    run_analysis_workflow,
    retrieve_business_knowledge,
    summarize_sales,
)


PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sales_large.csv"
TOOL_LABELS = {
    "get_sales_summary": "销售总览",
    "get_profit_by_product": "按产品统计利润",
    "get_profit_by_month": "按月份统计利润",
    "get_performance_by_region": "地区经营表现",
    "get_refund_risks": "退款与亏损风险",
    "get_business_insights": "自动洞察与建议",
    "get_channel_and_segment_performance": "渠道与客户类型表现",
    "search_business_knowledge": "RAG 业务知识检索",
}
load_dotenv(PROJECT_ROOT / ".env")


def load_uploaded_sales(
    uploaded_file: st.runtime.uploaded_file_manager.UploadedFile,
) -> pd.DataFrame:
    """Save an uploaded CSV temporarily, then load it with the shared validator."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temporary_file:
        temporary_file.write(uploaded_file.getbuffer())
        temporary_path = Path(temporary_file.name)

    try:
        return load_sales(temporary_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def filter_sales(
    sales: pd.DataFrame,
    start_date: object,
    end_date: object,
    regions: list[str],
    products: list[str],
    channels: list[str] | None = None,
    customer_segments: list[str] | None = None,
) -> pd.DataFrame:
    """Apply the dashboard filters without mutating the original data."""
    mask = (
        sales["date"].dt.date.between(start_date, end_date)
        & sales["region"].isin(regions)
        & sales["product"].isin(products)
    )
    if channels is not None and "channel" in sales.columns:
        mask &= sales["channel"].isin(channels)
    if customer_segments is not None and "customer_segment" in sales.columns:
        mask &= sales["customer_segment"].isin(customer_segments)
    return sales.loc[mask].copy()


def render_filters(sales: pd.DataFrame) -> pd.DataFrame:
    """Render global filters and return the selected subset."""
    minimum_date = sales["date"].min().date()
    maximum_date = sales["date"].max().date()
    all_regions = sorted(sales["region"].unique().tolist())
    all_products = sorted(sales["product"].unique().tolist())

    st.sidebar.header("分析范围")
    selected_dates = st.sidebar.date_input(
        "日期范围",
        value=(minimum_date, maximum_date),
        min_value=minimum_date,
        max_value=maximum_date,
    )
    selected_regions = st.sidebar.multiselect("地区", all_regions, default=all_regions)
    selected_products = st.sidebar.multiselect("产品", all_products, default=all_products)
    selected_channels = None
    selected_segments = None
    if "channel" in sales.columns:
        all_channels = sorted(sales["channel"].unique().tolist())
        selected_channels = st.sidebar.multiselect(
            "渠道", all_channels, default=all_channels
        )
    if "customer_segment" in sales.columns:
        all_segments = sorted(sales["customer_segment"].unique().tolist())
        selected_segments = st.sidebar.multiselect(
            "客户类型", all_segments, default=all_segments
        )

    if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
    else:
        start_date = end_date = selected_dates

    filtered = filter_sales(
        sales,
        start_date,
        end_date,
        selected_regions,
        selected_products,
        selected_channels,
        selected_segments,
    )
    st.sidebar.caption(f"当前显示 {len(filtered)} / {len(sales)} 笔订单")
    return filtered


def render_kpis(sales: pd.DataFrame) -> None:
    """Render decision-oriented KPIs and the latest monthly profit change."""
    summary = summarize_sales(sales)
    monthly = monthly_performance(sales)
    latest_growth = monthly.iloc[-1]["profit_growth"] if len(monthly) >= 2 else None
    growth_label = (
        f"{latest_growth:+.1f}% 较上月" if pd.notna(latest_growth) else None
    )

    columns = st.columns(5)
    columns[0].metric("订单数", f"{summary['order_count']:,}")
    columns[1].metric("销售额", f"¥{summary['total_revenue']:,.0f}")
    columns[2].metric("利润", f"¥{summary['total_profit']:,.0f}", growth_label)
    columns[3].metric("利润率", f"{summary['profit_margin']:.1f}%")
    columns[4].metric("退款金额", f"¥{summary['total_refunds']:,.0f}")


def render_insight_cards(sales: pd.DataFrame) -> None:
    """Show automatic findings paired with concrete follow-up actions."""
    st.subheader("自动洞察")
    st.caption("每条结论都来自当前筛选范围；建议用于定位问题，不代表因果判断。")
    insights = generate_business_insights(sales)
    columns = st.columns(2)
    for index, insight in enumerate(insights):
        with columns[index % 2].container(border=True):
            st.markdown(f"#### {insight['title']}")
            if insight["level"] == "warning":
                st.warning(insight["finding"])
            elif insight["level"] == "positive":
                st.success(insight["finding"])
            else:
                st.info(insight["finding"])
            st.markdown(f"**下一步：** {insight['action']}")


def render_overview(sales: pd.DataFrame) -> None:
    """Render executive overview, trends, insights, and report downloads."""
    render_kpis(sales)
    st.divider()
    monthly = monthly_performance(sales).set_index("month")
    product = performance_by_dimension(sales, "product").set_index("product")

    left, right = st.columns(2)
    with left:
        st.subheader("月度经营趋势")
        st.line_chart(monthly[["revenue", "profit"]], height=320)
    with right:
        st.subheader("产品利润贡献")
        st.bar_chart(product[["profit"]], height=320)

    render_insight_cards(sales)

    st.subheader("导出当前分析")
    report = build_analysis_report(sales)
    download_columns = st.columns(2)
    download_columns[0].download_button(
        "下载分析报告（Markdown）",
        data=report,
        file_name="sales_analysis_report.md",
        mime="text/markdown",
        width="stretch",
    )
    download_columns[1].download_button(
        "下载筛选后数据（CSV）",
        data=sales.to_csv(index=False).encode("utf-8-sig"),
        file_name="filtered_sales.csv",
        mime="text/csv",
        width="stretch",
    )


def render_trend_analysis(sales: pd.DataFrame) -> None:
    """Render monthly movements and the table behind the charts."""
    monthly = monthly_performance(sales)
    st.subheader("月度收入与利润")
    chart_data = monthly.set_index("month")
    st.line_chart(chart_data[["revenue", "profit"]], height=360)

    left, right = st.columns(2)
    with left:
        st.subheader("利润率变化")
        st.line_chart(chart_data[["profit_margin"]], height=280)
    with right:
        st.subheader("退款金额变化")
        st.bar_chart(chart_data[["refund_amount"]], height=280)

    display = monthly.rename(
        columns={
            "month": "月份",
            "order_count": "订单数",
            "revenue": "销售额",
            "profit": "利润",
            "refund_amount": "退款金额",
            "profit_margin": "利润率(%)",
            "profit_growth": "利润环比(%)",
        }
    )
    st.dataframe(display, width="stretch", hide_index=True)


def render_dimension_analysis(sales: pd.DataFrame, dimension: str) -> None:
    """Render product or region contribution and drill-down details."""
    dimension_label = {
        "product": "产品",
        "region": "地区",
        "channel": "渠道",
        "customer_segment": "客户类型",
    }[dimension]
    performance = performance_by_dimension(sales, dimension)
    display = performance.rename(
        columns={
            dimension: dimension_label,
            "order_count": "订单数",
            "quantity": "销量",
            "revenue": "销售额",
            "profit": "利润",
            "refund_amount": "退款金额",
            "profit_margin": "利润率(%)",
            "refund_rate": "退款率(%)",
        }
    )

    left, right = st.columns(2)
    with left:
        st.subheader(f"{dimension_label}利润")
        st.bar_chart(performance.set_index(dimension)[["profit"]], height=330)
    with right:
        st.subheader(f"{dimension_label}利润率")
        st.bar_chart(performance.set_index(dimension)[["profit_margin"]], height=330)
    st.dataframe(display, width="stretch", hide_index=True)

    selection = st.selectbox(
        f"选择一个{dimension_label}继续下钻",
        performance[dimension].tolist(),
        key=f"drilldown_{dimension}",
    )
    selected = sales[sales[dimension] == selection]
    st.markdown(f"#### {selection} 的月度表现")
    drilldown = monthly_performance(selected).set_index("month")
    st.line_chart(drilldown[["revenue", "profit"]], height=280)


def render_structure_analysis(sales: pd.DataFrame) -> None:
    """Render channel and customer-segment analysis when those fields exist."""
    if "channel" not in sales.columns or "customer_segment" not in sales.columns:
        st.info("当前数据缺少 channel 或 customer_segment 字段，无法分析经营结构。")
        return

    section_tabs = st.tabs(["渠道表现", "客户类型"])
    with section_tabs[0]:
        render_dimension_analysis(sales, "channel")
    with section_tabs[1]:
        render_dimension_analysis(sales, "customer_segment")


def render_risk_analysis(sales: pd.DataFrame) -> None:
    """Render refunded and loss-making orders with diagnostic context."""
    risks = find_risk_orders(sales)
    if risks.empty:
        st.success("当前筛选范围内没有退款或亏损订单。")
        return

    loss_orders = int((risks["profit"] < 0).sum())
    columns = st.columns(3)
    columns[0].metric("风险订单", len(risks))
    columns[1].metric("亏损订单", loss_orders)
    columns[2].metric("涉及退款", f"¥{risks['refund_amount'].sum():,.0f}")
    st.warning("优先检查同时出现退款和负利润的订单；异常提示不等同于原因结论。")
    display = risks.rename(
        columns={
            "order_id": "订单号",
            "date": "日期",
            "region": "地区",
            "product": "产品",
            "revenue": "销售额",
            "refund_amount": "退款金额",
            "profit": "利润",
            "risk_reason": "风险原因",
        }
    )
    st.dataframe(display, width="stretch", hide_index=True)


def render_dashboard(sales: pd.DataFrame) -> None:
    """Render the multi-view analysis cockpit."""
    tabs = st.tabs(
        [
            "经营总览",
            "趋势分析",
            "产品分析",
            "地区分析",
            "渠道与客群",
            "风险订单",
            "数据明细",
        ]
    )
    with tabs[0]:
        render_overview(sales)
    with tabs[1]:
        render_trend_analysis(sales)
    with tabs[2]:
        render_dimension_analysis(sales, "product")
    with tabs[3]:
        render_dimension_analysis(sales, "region")
    with tabs[4]:
        render_structure_analysis(sales)
    with tabs[5]:
        render_risk_analysis(sales)
    with tabs[6]:
        st.subheader("筛选后的订单明细")
        st.dataframe(sales, width="stretch", hide_index=True)


def clear_agent_memory() -> None:
    """Clear both the visible transcript and the SDK replay history."""
    st.session_state.pop("chat_messages", None)
    st.session_state.pop("agent_history", None)


def render_tool_steps(tool_steps: list[dict[str, object]], status: str) -> None:
    """Render the tools used during one assistant turn."""
    with st.expander("查看本轮执行过程", expanded=True):
        if tool_steps:
            for index, step in enumerate(tool_steps, start=1):
                tool_name = str(step["tool_name"])
                tool_label = TOOL_LABELS.get(tool_name, "未知工具")
                st.markdown(f"**步骤 {index}：选择工具** `{tool_name}`（{tool_label}）")
                if step["arguments"]:
                    st.markdown("传入参数：")
                    st.json(step["arguments"])
                st.markdown("工具返回：")
                st.json(step["output"])
            st.markdown("**最后：模型根据工具返回的数据生成回答。**")
        elif status == "unsupported":
            st.write("Agent 判断现有工具不足，因此没有调用数据工具。")
        else:
            st.write("这次回答直接使用了对话上下文，没有再次调用数据工具。")


def render_chat_history() -> None:
    """Render all user and assistant turns saved for this browser session."""
    for message in st.session_state.get("chat_messages", []):
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                if message["status"] == "unsupported":
                    st.warning(f"超出当前能力范围：{message['content']}")
                    if message["missing_capability"]:
                        st.caption(f"缺少能力：{message['missing_capability']}")
                else:
                    st.markdown(message["content"])
                render_tool_steps(message["tool_steps"], message["status"])
            else:
                st.markdown(message["content"])


def render_agent_question(sales: pd.DataFrame) -> None:
    """Render a multi-turn question box and run the agent after a button click."""
    data_fingerprint = int(pd.util.hash_pandas_object(sales, index=True).sum())
    previous_fingerprint = st.session_state.get("data_fingerprint")
    if previous_fingerprint is not None and previous_fingerprint != data_fingerprint:
        clear_agent_memory()
        st.info("筛选范围或数据源已变化，旧对话记忆已自动清空。")
    st.session_state["data_fingerprint"] = data_fingerprint
    st.session_state.setdefault("chat_messages", [])

    st.subheader("向 Agent 继续追问")
    st.caption(
        "支持销售总览、趋势、产品、地区、渠道、客群、退款风险和分析建议；"
        "不预测未来，也不把相关性说成因果关系。"
    )
    st.info(
        "可以试试：哪个地区利润率最低？｜超过 3,000 元退款需要谁复核？｜"
        "East 的退款率达到手册重点复核阈值了吗？"
    )
    question = st.text_input(
        "你想了解什么？",
        placeholder="例如：哪个地区利润率最低，可能需要检查什么？",
        max_chars=MAX_QUESTION_LENGTH,
    )

    button_columns = st.columns([1, 1, 4])
    ask_clicked = button_columns[0].button("让 Agent 分析", type="primary")
    clear_clicked = button_columns[1].button("清空对话")

    if clear_clicked:
        clear_agent_memory()
        st.rerun()

    if ask_clicked:
        if not question.strip():
            st.warning("请先输入一个问题。")
        elif not os.getenv("OPENAI_API_KEY"):
            st.error(
                "没有找到 API Key。云端请检查 Streamlit Secrets，"
                "本地请检查项目根目录的 .env 文件。"
            )
        else:
            with st.spinner("Agent 正在选择工具并分析当前筛选范围……"):
                try:
                    agent_run = asyncio.run(
                        run_data_agent(
                            sales,
                            question,
                            history=st.session_state.get("agent_history"),
                        )
                    )
                except ValueError as error:
                    st.warning(str(error))
                except MaxTurnsExceeded:
                    st.error("Agent 调用工具的轮次过多，请简化问题后重试。")
                except ModelBehaviorError:
                    st.error("Agent 返回格式异常，请重新提问。")
                except OpenAIError as error:
                    st.error(describe_openai_error(error, "Agent 请求失败"))
                except AgentsException:
                    st.error("Agent 运行失败，请清空对话后重试。")
                else:
                    tool_steps = [
                        {
                            "tool_name": step.tool_name,
                            "arguments": step.arguments,
                            "output": step.output,
                        }
                        for step in agent_run.tool_steps
                    ]
                    st.session_state["agent_history"] = agent_run.history
                    st.session_state["chat_messages"].extend(
                        [
                            {"role": "user", "content": question.strip()},
                            {
                                "role": "assistant",
                                "content": agent_run.answer,
                                "status": agent_run.status,
                                "missing_capability": agent_run.missing_capability,
                                "tool_steps": tool_steps,
                            },
                        ]
                    )

    render_chat_history()


def render_knowledge_base() -> None:
    """Render RAG index details and semantic retrieval results."""
    st.subheader("业务知识库与 RAG 检索")
    st.caption("以下规则均为学习项目的虚构演示资料，不代表真实公司的政策。")

    try:
        chunks = load_knowledge_chunks(PROJECT_ROOT / "knowledge")
        index = load_knowledge_index()
    except (FileNotFoundError, ValueError) as error:
        st.error(str(error))
        return

    metric_columns = st.columns(3)
    metric_columns[0].metric("知识文档", len({chunk.source for chunk in chunks}))
    metric_columns[1].metric("检索知识块", len(index.chunks))
    metric_columns[2].metric("Embedding 模型", EMBEDDING_MODEL)

    with st.expander("RAG 是怎么工作的？", expanded=True):
        st.code(
            "Markdown 文档 → 按章节切块 → Embedding 向量索引\n"
            "用户问题 → 问题向量 → 余弦相似度排序 → 返回相关段落和来源"
        )
        for source in sorted({chunk.source for chunk in chunks}):
            section_names = [
                chunk.section_title for chunk in chunks if chunk.source == source
            ]
            st.markdown(f"- `{source}`：{'、'.join(section_names)}")

    query = st.text_input(
        "检索业务知识库",
        placeholder="例如：退款超过 3,000 元需要哪些复核？",
        key="rag_query",
    )
    search_clicked = st.button("检索知识库", type="primary")
    if search_clicked:
        if not query.strip():
            st.warning("请先输入要检索的问题。")
        elif not os.getenv("OPENAI_API_KEY"):
            st.error(
                "没有找到 API Key。云端请检查 Streamlit Secrets，"
                "本地请检查项目根目录的 .env 文件。"
            )
        else:
            with st.spinner("正在生成问题向量并检索最相关知识块……"):
                try:
                    st.session_state["knowledge_hits"] = retrieve_business_knowledge(
                        query, top_k=4
                    )
                except OpenAIError as error:
                    st.error(describe_openai_error(error, "Embedding 请求失败"))
                except (FileNotFoundError, ValueError) as error:
                    st.error(str(error))

    hits = st.session_state.get("knowledge_hits", [])
    if hits:
        st.subheader("检索结果")
        for index_number, hit in enumerate(hits, start=1):
            with st.container(border=True):
                st.markdown(
                    f"#### {index_number}. {hit.section_title} "
                    f"· 相似度 {hit.score:.3f}"
                )
                st.caption(hit.citation)
                st.write(hit.content)


def render_report_workflow(sales: pd.DataFrame) -> None:
    """Render the planner → evidence → writer workflow and its trace."""
    report_fingerprint = int(pd.util.hash_pandas_object(sales, index=True).sum())
    previous_fingerprint = st.session_state.get("report_data_fingerprint")
    if previous_fingerprint is not None and previous_fingerprint != report_fingerprint:
        st.session_state.pop("analysis_workflow_run", None)
        st.info("筛选范围已变化，旧报告已清空，请重新生成。")
    st.session_state["report_data_fingerprint"] = report_fingerprint

    st.subheader("生成 Agent 深度分析报告")
    st.caption(
        "工作流会先规划分析模块，再由本地代码计算证据，最后让报告 Agent 基于证据写作。"
    )
    request = st.text_area(
        "这份报告要重点解决什么问题？",
        value="分析整体经营表现，定位利润、渠道和退款风险，并给出下一步核查建议。",
        max_chars=500,
        height=100,
    )
    generate_clicked = st.button("生成深度报告", type="primary")

    if generate_clicked:
        if not request.strip():
            st.warning("请先填写报告目标。")
        elif not os.getenv("OPENAI_API_KEY"):
            st.error(
                "没有找到 API Key。云端请检查 Streamlit Secrets，"
                "本地请检查项目根目录的 .env 文件。"
            )
        else:
            with st.spinner("规划 Agent 正在选择分析路线并生成报告……"):
                try:
                    workflow_run = asyncio.run(
                        run_analysis_workflow(sales, request)
                    )
                except ValueError as error:
                    st.warning(str(error))
                except MaxTurnsExceeded:
                    st.error("报告工作流轮次过多，请缩小报告目标后重试。")
                except ModelBehaviorError:
                    st.error("Agent 返回的计划或报告格式异常，请重新生成。")
                except OpenAIError as error:
                    st.error(describe_openai_error(error, "报告请求失败"))
                except AgentsException:
                    st.error("报告工作流运行失败，请稍后重试。")
                else:
                    st.session_state["analysis_workflow_run"] = workflow_run

    workflow_run = st.session_state.get("analysis_workflow_run")
    if workflow_run is None:
        st.info("生成后，这里会显示 Agent 的分析计划、证据模块和结构化报告。")
        return

    with st.expander("查看工作流执行过程", expanded=True):
        st.markdown("**步骤 1：规划 Agent 选择分析模块**")
        st.json(workflow_run.plan.model_dump())
        st.markdown("**步骤 2：本地工具收集并计算数据证据**")
        st.write("已完成模块：", "、".join(workflow_run.evidence.keys()))
        st.markdown("**步骤 3：报告 Agent 仅根据上述证据生成报告**")

    report = workflow_run.report
    st.title(report.title)
    st.info(report.executive_summary)
    st.subheader("主要发现")
    for finding in report.findings:
        with st.container(border=True):
            st.markdown(f"#### {finding.title}")
            st.markdown(f"**数据依据：** {finding.evidence}")
            st.write(finding.interpretation)
            st.markdown(f"**下一步：** {finding.next_step}")

    left, right = st.columns(2)
    with left:
        st.subheader("风险提示")
        for alert in report.risk_alerts:
            st.warning(alert)
    with right:
        st.subheader("建议动作")
        for index, action in enumerate(report.recommended_actions, start=1):
            st.markdown(f"{index}. {action}")

    with st.expander("分析限制"):
        for limitation in report.limitations:
            st.write(f"- {limitation}")

    st.download_button(
        "下载 Agent 报告（Markdown）",
        data=analysis_report_to_markdown(workflow_run),
        file_name="agent_deep_analysis_report.md",
        mime="text/markdown",
        width="stretch",
    )


st.set_page_config(page_title="智能数据分析 Agent", page_icon="📊", layout="wide")
st.title("智能数据分析 Agent")
st.caption("从多维数据探索、风险定位到 Agent 规划与深度报告的交互式分析工作台。")

uploaded_file = st.sidebar.file_uploader("上传销售 CSV", type=["csv"])
data_source = "上传文件" if uploaded_file is not None else "内置示例数据"

try:
    sales_data = (
        load_uploaded_sales(uploaded_file)
        if uploaded_file is not None
        else load_sales(SAMPLE_DATA_PATH)
    )
    filtered_sales = render_filters(sales_data)
    st.caption(f"数据源：{data_source} · 当前分析 {len(filtered_sales)} 笔订单")

    if filtered_sales.empty:
        st.warning("当前筛选条件下没有订单，请调整日期、地区或产品。")
    else:
        workspace_tabs = st.tabs(
            [
                "📊 分析驾驶舱",
                "🤖 Agent 分析",
                "📚 业务知识库",
                "📝 Agent 报告",
            ]
        )
        with workspace_tabs[0]:
            render_dashboard(filtered_sales)
        with workspace_tabs[1]:
            render_agent_question(filtered_sales)
        with workspace_tabs[2]:
            render_knowledge_base()
        with workspace_tabs[3]:
            render_report_workflow(filtered_sales)
except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
    st.error(f"无法分析这份数据：{error}")
