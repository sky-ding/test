# 项目管理登记工具

前后端分目录：**前端**静态页面在 `frontend/`，**后端**为 `backend/`（FastAPI + SQLite）。

## 目录说明

| 路径 | 说明 |
|------|------|
| `frontend/index.html` | 当前主页面（单文件，后续可拆 CSS/JS） |
| `backend/` | Python FastAPI 服务与持久化 |
| `docs/` | PRD、技术设计、用户操作指南 |

## 重要提示

- **不要用 `file://` 直接双击打开** `index.html` 调用后端 API（浏览器会限制跨域与协议）。请用 **HTTP 静态服务** 访问前端，例如：  
  `npx serve frontend -l 3000`  
  然后浏览器打开 <http://127.0.0.1:3000>。
- 前端当前仍主要使用 **浏览器 localStorage** 保存数据；对接服务端需将保存/加载改为调用 `http://127.0.0.1:8000/api/v1/...`（后续迭代）。

## 启动后端

详见 [backend/README.md](backend/README.md)。

简要步骤：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 启动前端（静态）

在项目根目录：

```bash
npx --yes serve frontend -l 3000
```

## 一键同时启动（可选）

根目录已提供 `package.json`，需先安装 Node 依赖并完成 **后端 venv 与 pip 安装** 后：

```bash
npm install
npm run dev
```

将并行启动：

- 后端：<http://127.0.0.1:8000>
- 前端：<http://127.0.0.1:3000>

若 `npm run dev:backend` 找不到依赖，请在已激活的 `backend/.venv` 环境中手动执行 `uvicorn`（见上文）。

## CORS

默认允许 `http://127.0.0.1:3000`、`localhost:3000`、`5500`、`8080` 等。其他端口可设置环境变量：

```bash
set PM_CORS_ORIGINS=http://127.0.0.1:4173,http://localhost:4173
```

（Linux/macOS 使用 `export`。）
