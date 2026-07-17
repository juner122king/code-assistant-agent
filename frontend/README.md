# Frontend (Vue 3 + Vite)

Code Assistant Agent 的 Web UI：分析表单 + 报告展示。

## 开发

后端先启动（项目根目录）：

```bash
export PYTHONPATH=.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

然后：

```bash
npm install
npm run dev
```

访问 http://127.0.0.1:5173 （`/analyze` 等由 Vite 代理到 8000）。

## 构建（供 FastAPI 托管）

```bash
npm run build
```

产物在 `dist/`。后端 `app/main.py` 会在存在 `frontend/dist/index.html` 时挂载静态 SPA。
