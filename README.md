# Code Assistant Agent

学习型 **AI Agent 应用** 练手项目：输入一个代码仓库，Agent 通过 **工具调用闭环** 自动理解项目，并输出：

- **项目结构**
- **风险**
- **Bug**

目标形态接近 Claude Code / Cursor Agent / Copilot Workspace 的「分析模式」，**不是** ChatGPT 式聊天框。

## 架构（核心学习点）

```
POST /analyze { repo }
        │
        ▼
  resolve_repo  ──► LocalFsBackend 或 GitHubBackend
        │
        ▼
   AgentLoop（多步）
        │
        ├─► Claude Messages API（tools=...）
        │         │
        │         ▼ tool_use
        ├─► ToolRegistry.execute
        │         │
        │         ▼
        │    list_directory_tree / read_file / search_files / get_repo_meta
        │         │
        │         ▼ tool_result 写回 messages
        └─► 直到模型输出 JSON 报告
```

关键模块：

| 路径 | 职责 |
|------|------|
| `app/agent/loop.py` | Agent 主循环（ReAct / tool-use） |
| `app/tools/registry.py` | Tool schema 与执行分发 |
| `app/repo/*` | 本地文件系统 / GitHub API 统一后端 |
| `app/llm/claude_client.py` | Claude API 封装 |
| `app/api/routes.py` | FastAPI HTTP 接口 |

## 快速开始

### 1. 环境

需要 Python 3.9+。

```bash
cd code-assistant-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY
```

可选：设置 `GITHUB_TOKEN` 以提高 GitHub API 限额或读取私有仓库。

### 2. 启动服务

```bash
# 在项目根目录
export PYTHONPATH=.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开文档：http://127.0.0.1:8000/docs

### 3. 调用分析

**本地仓库（内置有问题的示例）：**

```bash
curl -s -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d "{\"repo\": \"$(pwd)/tests/fixtures/sample_repo\"}" | python3 -m json.tool
```

**GitHub 公有仓库：**

```bash
curl -s -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"repo": "https://github.com/psf/requests", "focus": "general"}' | python3 -m json.tool
```

响应字段：

- `structure`：摘要、目录预览、技术栈
- `risks` / `bugs`：带 severity 与 evidence
- `tool_calls`：工具调用轨迹（观察 Agent 行为）
- `agent_steps`：循环步数

## 运行测试（不调用 Claude）

```bash
export PYTHONPATH=.
pytest -q
```

覆盖：路径解析、本地沙箱、工具注册执行。

## 设计说明（给学习者）

1. **工具决定观察，模型决定策略**  
   上下文不预先塞满全库代码；由模型决定下一步 `list` / `read` / `search`。

2. **RepoBackend 抽象**  
   本地与 GitHub 共用同一 Tool 层，Agent 逻辑与数据源解耦。

3. **护栏**  
   `AGENT_MAX_STEPS`、文件字节上限、树条目上限、本地路径沙箱（防 `../` 逃逸）。

4. **MVP 边界**  
   当前只做「读 + 分析报告」。后续可扩展：流式输出、自动修代码、开 PR、多 Agent 分工。

## 环境变量

见 `.env.example`：

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | 必填 |
| `ANTHROPIC_MODEL` | 默认 `claude-sonnet-5`，可按账号可用模型调整 |
| `GITHUB_TOKEN` | 可选 |
| `AGENT_MAX_STEPS` | 默认 12 |
| `AGENT_MAX_FILE_BYTES` | 单文件读取上限 |
| `AGENT_MAX_TREE_ENTRIES` | 目录树条目上限 |

## 项目结构

```
code-assistant-agent/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/routes.py
│   ├── agent/          # loop / prompts / session
│   ├── tools/          # registry + 4 个 MVP tools
│   ├── repo/           # local + github
│   ├── llm/            # Claude client
│   └── models/         # 请求/响应 Pydantic
├── tests/
│   ├── fixtures/sample_repo/   # 故意有漏洞的示例仓
│   └── test_*.py
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT（学习用途）
