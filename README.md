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
        ├─► LLM（Anthropic Messages 或 OpenAI chat.completions）
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
| `app/llm/` | Claude / OpenAI 兼容客户端 |
| `app/api/routes.py` | FastAPI HTTP 接口 |
| `frontend/` | Vue 3 + Vite 分析表单与报告 UI |

## 快速开始

### 1. 环境

需要 **Python 3.9+**。前端构建需要 **Node.js 18+**。

```bash
cd code-assistant-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：默认走硅基流动 OpenAI 兼容 API
# LLM_PROVIDER=openai
# LLM_BASE_URL=https://api.siliconflow.cn/v1
# LLM_API_KEY=...
# LLM_MODEL=Qwen/Qwen3-8B
```

可选：设置 `GITHUB_TOKEN` 以提高 GitHub API 限额或读取私有仓库。

### 2. 启动后端

```bash
# 在项目根目录
export PYTHONPATH=.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：http://127.0.0.1:8000/docs  
- 健康检查：http://127.0.0.1:8000/health  
- 同步分析：`POST /analyze`（可选 `max_steps` 1–40，覆盖默认 `AGENT_MAX_STEPS`）  
- **流式分析（推荐 UI）**：`POST /analyze/stream`（SSE；同样支持 `max_steps`、`model`）  
- **分析记录**：`GET /analyze/runs`、`GET /analyze/runs/{id}`（含过程事件）、`DELETE /analyze/runs/{id}`  
- **模型目录**：`GET /analyze/models`（适合代码分析的免费/付费模型与性价比）  
  - 事件：`start` / `step` / `tool` / `status` / `done` / `error`  
  - 前端开发模式会实时展示 Agent 步骤与工具调用时间线  
- **从 Bug 修复**：  
  - `POST /fix/propose` / `POST /fix/propose/stream` — 生成 diff 提案（不落盘）  
  - `POST /fix/apply` — 确认后写入本地路径  
  - `POST /fix/open-pr` — 确认后经 GitHub API 建分支并开 PR（需 `GITHUB_TOKEN`）  
  - `GET /fix/{fix_id}` — 查询未过期提案  

### 3. 前端 UI（Vue 3 + Vite）

#### 开发模式（热更新 + 代理）

终端 1 保持 uvicorn 运行，终端 2：

```bash
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173 。Vite 会把 `/analyze`、`/analyze/stream`、`/health` 代理到 `8000`。

#### 生产模式（同源单端口）

```bash
cd frontend
npm install
npm run build
# 生成 frontend/dist/

# 回到项目根，启动（或重启）uvicorn
export PYTHONPATH=.
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开 http://127.0.0.1:8000/ 即可使用 UI（FastAPI 托管静态 SPA）。  
未执行 `npm run build` 时，`GET /` 返回 JSON 提示如何构建前端。

> **说明：** 表单中的「本地路径」是 **运行 uvicorn 的机器** 上的路径，不是浏览器本机路径。演示可用仓库内 `tests/fixtures/sample_repo` 的绝对路径，或 GitHub URL。

分析可能经历多步工具调用（默认最多 8 步），前端请求超时约 10 分钟。步数越大越慢。

### 4. 调用分析（curl）

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

4. **修复流程（先审后写）**  
   Bug 列表 → `POST /fix/propose`（只读生成 patch）→ 用户确认 →  
   本地 `POST /fix/apply` 或 GitHub `POST /fix/open-pr`（API 无 clone）。

## 环境变量

见 `.env.example`：

| 变量 | 说明 |
|------|------|
| `LLM_PROVIDER` | `openai`（硅基流动）或 `anthropic`（旧中转） |
| `LLM_BASE_URL` | OpenAI 兼容网关，默认 `https://api.siliconflow.cn/v1` |
| `LLM_API_KEY` | 硅基流动 API Key |
| `LLM_MODEL` | 默认 `Qwen/Qwen3-8B`；请求体也可传 `model` 覆盖 |
| `ANALYZE_HISTORY_MAX` | 分析记录条数上限，默认 50 |
| `LLM_ENABLE_THINKING` | 默认 `false`；Qwen3 tool 循环不要开 |
| `ANTHROPIC_API_KEY` | 可选；与 AUTH_TOKEN 二选一（`LLM_PROVIDER=anthropic`） |
| `ANTHROPIC_AUTH_TOKEN` | 私有中转密钥 |
| `ANTHROPIC_BASE_URL` | Anthropic 兼容中转 |
| `ANTHROPIC_MODEL` | Anthropic 路径模型 ID |
| `GITHUB_TOKEN` | 可选 |
| `AGENT_MAX_STEPS` | 默认 8 |
| `AGENT_TOOL_MAX_TOKENS` | 中间 tool 步 max_tokens，默认 1024 |
| `LLM_STEP_DELAY_SECONDS` | 步间等待；硅基流动建议 0 |
| `AGENT_MAX_FILE_BYTES` | 单文件读取上限 |
| `AGENT_MAX_TREE_ENTRIES` | 目录树条目上限 |

## 项目结构

```
code-assistant-agent/
├── app/
│   ├── main.py           # FastAPI 入口 + 可选托管 frontend/dist
│   ├── config.py
│   ├── api/routes.py
│   ├── agent/            # loop / prompts / session
│   ├── tools/            # registry + 4 个 MVP tools
│   ├── repo/             # local + github
│   ├── llm/              # Claude / OpenAI 兼容客户端
│   └── models/           # 请求/响应 Pydantic
├── frontend/             # Vue 3 + Vite UI
│   ├── src/
│   │   ├── App.vue
│   │   ├── api/analyze.js
│   │   └── components/
│   ├── package.json
│   └── vite.config.js    # dev 代理到 :8000
├── tests/
│   ├── fixtures/sample_repo/   # 故意有漏洞的示例仓
│   └── test_*.py
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT（学习用途）
