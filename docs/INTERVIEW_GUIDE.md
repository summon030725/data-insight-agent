# 面试讲解稿

## 30 秒项目介绍

我做了一个智能销售数据分析 Agent。它不是让大模型直接计算 CSV，而是让模型负责理解问题和选择工具，再由 Pandas 完成可靠的数据计算。项目还加入了基于 OpenAI Embedding 的 RAG 知识库，可以同时回答经营数据和业务政策问题。对于复杂任务，我把流程拆成规划 Agent、证据收集和报告 Agent，并通过 31 项离线测试和 8 个真实 Agent 用例做回归评测。

## 2 分钟演示顺序

1. 打开经营总览，介绍 1,500 条、18 个月的演示数据。
2. 使用地区、产品、渠道和客群筛选器展示联动效果。
3. 打开风险订单，展示退款和负利润识别。
4. 向 Agent 提问“East 地区退款率达到手册阈值了吗？”
5. 展示 Agent 同时调用地区工具和 RAG 工具的执行轨迹。
6. 打开业务知识库，展示 Chunk、Embedding、相似度和来源。
7. 生成深度报告，展示规划、证据收集和报告三个阶段。
8. 最后说明测试结果和能力边界。

## 最重要的技术难点

### 1. 防止模型编造数字

问题：大模型不适合直接对大量表格做精确聚合，容易出现数字错误。

方案：把销售汇总、趋势、利润率和风险排序做成确定性 Python 工具。模型只能根据工具结果回答。

结果：最终答案中的关键数字可以通过单元测试和 Agent Evals 验证。

### 2. 处理结构化数据和非结构化知识

问题：CSV 适合计算，而退款政策和操作手册适合文本检索，单一方案无法同时做好。

方案：数据问题使用 Pandas 工具，政策问题使用 RAG，混合问题由 Agent 同时调用两种能力。

结果：系统既能回答“退款率是多少”，也能回答“是否达到手册阈值”，并提供来源。

### 3. 控制复杂报告的幻觉

问题：直接要求模型写完整报告，容易扩写没有数据支持的结论。

方案：先由规划 Agent 选择模块，再由代码收集证据，最后把计划和证据交给报告 Agent。报告 Agent 通过 Pydantic 输出固定结构。

结果：每条发现都有数据依据、谨慎解读和下一步动作。

### 4. 让 Agent 可调试

问题：只展示最终答案，很难知道 Agent 为什么出错。

方案：记录每次工具调用、参数和返回值，并在网页展示；深度报告也展示计划和证据模块。

结果：可以区分是工具选择错误、工具数据错误，还是模型表达错误。

### 5. 评测非确定性系统

问题：模型每次措辞可能不同，不能只做字符串完全匹配。

方案：评测可观察行为，包括状态、工具集合和必要事实；RAG 用例还检查来源引用。

结果：目前 8 个真实 Agent 用例全部通过，并有 31 项离线测试覆盖确定性模块。

## 高频面试问题

### 这和普通聊天机器人有什么区别？

普通聊天机器人主要生成文本。这个项目会选择并执行工具、保存状态、检索知识、运行多阶段工作流，并对工具行为做评测。

### 为什么没有使用 LangChain？

我先使用 OpenAI Agents SDK 和自己编写的编排代码，目的是理解工具调用、状态、结构化输出和工作流的底层原理。当前架构已经模块化，后续可以把报告工作流迁移到 LangGraph，获得持久化和人工审批能力。

### RAG 的完整过程是什么？

文档按标题切成 Chunk，批量生成 Embedding 并保存本地索引。查询时只生成问题向量，计算余弦相似度，选出最相关的四段，然后把文本和来源返回给 Agent。

### 为什么不用 RAG 计算利润？

RAG 适合查找文本，不保证精确聚合。利润、总和和排名必须交给 Pandas 或 SQL；RAG 用于政策和业务说明。

### 如何避免 RAG 检索到错误内容？

当前会显示相似度和 Top K 来源，并要求 Agent保留引用。进一步可以加入相似度阈值、混合检索、重排序器和人工反馈数据集。

### 如果数据规模变成一亿条怎么办？

把 CSV/Pandas 工具替换为数据库或数据仓库查询，限制查询范围并返回聚合结果；Agent 接口可以保持不变。向量索引则迁移到 pgvector、Milvus 或托管向量数据库。

### 如何控制 API 成本？

选择低成本模型；聚合在本地完成；文档 Embedding 只在索引更新时生成一次；查询只嵌入短问题；回归评测使用小型固定用例。

### 项目有哪些不足？

当前数据和政策都是演示资料；没有真实权限系统；本地 JSON 向量索引不适合超大知识库；工作流状态没有持久化；缺少在线监控和用户反馈闭环。

## 简历项目描述

### 中文版本

- 基于 OpenAI Agents SDK、Pandas 与 Streamlit 开发智能销售数据分析 Agent，设计 8 个 Function Tools，支持多轮问答、能力边界和可观测执行轨迹。
- 实现 Embedding RAG 知识库，将 4 份 Markdown 文档切分为 19 个知识块，支持来源引用以及结构化数据与政策知识的混合问答。
- 构建“规划 Agent—确定性证据收集—报告 Agent”多阶段工作流，通过 Pydantic 约束报告结构，降低无依据结论。
- 建立 31 项离线测试和 8 个真实 Agent 回归评测，覆盖工具选择、关键事实、拒答行为与 RAG 引用。

### English version

- Built an intelligent sales analytics agent with OpenAI Agents SDK, Pandas, and Streamlit, exposing eight function tools with multi-turn state, explicit capability boundaries, and observable tool traces.
- Implemented an embedding-based RAG pipeline over 19 Markdown chunks, supporting source citations and hybrid reasoning across structured sales data and business policies.
- Designed a staged planner-evidence-writer workflow with Pydantic structured outputs to keep generated reports grounded in deterministic calculations.
- Added 31 offline tests and eight live agent regression cases covering tool routing, required facts, refusal behavior, and RAG citations.

## 可以继续扩展的方向

- 使用 LangGraph 实现持久化、重试、人工审批和中断恢复。
- 接入 PostgreSQL 与 pgvector。
- 增加 reranker、混合检索和 RAG 检索指标。
- 增加登录、权限隔离和 API 用量限制。
- 收集真实用户问题，持续扩充 Agent Evals。
