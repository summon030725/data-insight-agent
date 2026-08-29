# Streamlit Community Cloud 部署说明

## 当前状态

项目已经具备部署所需的依赖文件、入口文件、预构建数据和向量索引。目前本地仓库没有 GitHub 远程地址，因此公开部署前需要先创建 GitHub 仓库。

## 1. 发布到 GitHub

在 GitHub 创建一个空仓库，例如 `sales-data-agent`。不要勾选自动创建 README、`.gitignore` 或许可证。

然后在项目目录运行：

```powershell
git add .
git commit -m "Build intelligent sales analytics agent"
git remote add origin https://github.com/YOUR_NAME/sales-data-agent.git
git push -u origin master
```

提交前检查：

```powershell
git status
git check-ignore .env
git check-ignore .streamlit/secrets.toml
```

`.env` 和 `.streamlit/secrets.toml` 必须保持忽略状态。

## 2. 创建 Streamlit Cloud 应用

1. 打开 [Streamlit Community Cloud](https://share.streamlit.io/)。
2. 使用 GitHub 登录并授权读取目标仓库。
3. 点击 **Create app**。
4. 选择仓库和 `master` 分支。
5. Entry point 填写 `streamlit_app.py`。
6. 在 Advanced settings 中选择 Python 3.12。

## 3. 配置 API Key

在 Advanced settings 的 Secrets 中填写：

```toml
OPENAI_API_KEY = "你的新 API Key"
```

不要把真实 Key 写入 GitHub、README、`.env.example` 或任何截图。

Streamlit 会把根级 Secret 同时作为环境变量提供，因此 OpenAI SDK 可以读取 `OPENAI_API_KEY`。

## 4. 部署后检查

- 经营总览可以正常加载 1,500 条演示数据。
- 产品、地区、渠道和客群筛选器可以联动。
- “检索知识库”能返回来源和相似度。
- Agent 能回答数据问题和政策问题。
- 深度报告可以完成规划、取证和写作。
- 下载按钮能导出 CSV 和 Markdown。

## 5. 成本与安全

- 页面展示和本地数据分析不调用模型。
- Agent 问答、报告生成和 RAG 查询会产生 API 费用。
- 公开应用建议增加访问控制、速率限制或每日预算，避免 Key 被匿名用户持续消耗。
- 如果只是投递作品，可以先在面试期间短期开启，或将公开版本的 Agent 按钮改为演示模式。

## 常见问题

### `ModuleNotFoundError: data_agent`

确认根目录存在 `requirements.txt`，其中包含 `-e .`，并确认 `pyproject.toml` 已提交。

### 找不到 API Key

在 Streamlit Cloud 的 App settings → Secrets 中添加根级 `OPENAI_API_KEY`，然后重启应用。

### 找不到知识库索引

确认 `data/knowledge_index.json` 已提交。知识文档更新后，在本地重新运行：

```powershell
.\.venv\Scripts\python.exe scripts\build_knowledge_index.py
```

然后提交更新后的索引文件。
