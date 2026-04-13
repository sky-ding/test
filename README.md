# 项目管理登记工具

前后端分目录：**前端**静态页面在 `frontend/`，**后端**为 `backend/`（FastAPI + SQLite）。

## 目录说明

| 路径 | 说明 |
|------|------|
| `frontend/index.html` | 主应用（需先登录） |
| `frontend/login.html` | 登录页 |
| `backend/` | Python FastAPI 服务与持久化 |
| `docs/` | PRD、技术设计、用户操作指南（**当前文档版本 v1.2**，与登录鉴权等实现一致） |

## 重要提示

- **不要用 `file://` 直接双击打开** `index.html`（无法携带登录 Cookie）。请用 **HTTP 静态服务** 访问前端，例如：  
  `npx serve frontend -l 3000`  
  然后打开 <http://127.0.0.1:3000/login.html> 登录，或访问 <http://127.0.0.1:3000> 时未登录会自动跳转到登录页。
- 前端默认 API 地址为 `http://127.0.0.1:8001`，可在页面加载前设置 `window.PM_API_BASE`（见 `index.html` / `login.html` 内脚本）。
- **会话 Cookie**：登录后浏览器会保存 `pm_session`。开发环境下前端在 **3000** 端口、API 在 **8001** 端口属于**跨站**，部分浏览器对第三方 Cookie 较严格；若登录后仍被反复踢回登录页，请使用 **反向代理将前端与 `/api` 配成同源**，或查阅下文环境变量调整 `PM_SESSION_SAME_SITE` / `PM_SESSION_HTTPS_ONLY`（生产环境务必 HTTPS + 同源）。
- 业务数据仍主要保存在 **localStorage**；服务端 `registry` API 已需登录，**写操作仅管理员**。

## 鉴权与环境变量（首次部署必读）

在 **`backend` 目录**首次启动前建议设置（Windows 可用 `set`，Linux/macOS 用 `export`）：

| 变量 | 说明 |
|------|------|
| `PM_SESSION_SECRET` | 会话签名密钥，**生产必填**（勿使用仓库默认值） |
| `PM_SKY_INITIAL_PASSWORD` | 可选。覆盖首次创建 **`Sky`** 的初始密码；**不设置时默认为 `123123`**（生产请改为强密码并建议设置本变量） |
| `PM_AUTH_DISABLED` | 设为 `true` 时关闭鉴权（**仅本地调试**，勿用于生产） |
| `PM_SESSION_SAME_SITE` | Cookie `SameSite`，默认 `lax`；跨站调试可试 `none`（常需配合 HTTPS） |
| `PM_SESSION_HTTPS_ONLY` | Cookie 是否仅 HTTPS，默认 `false`（本地 HTTP 开发） |

示例（PowerShell）：

```powershell
cd backend
$env:PM_SESSION_SECRET="your-long-random-secret"
# 可选：覆盖 Sky 初始密码（默认 123123）
# $env:PM_SKY_INITIAL_PASSWORD="YourSecurePwd123"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

首次启动后可用用户名 **Sky**、密码 **123123** 登录（若未设置 `PM_SKY_INITIAL_PASSWORD`）。若库中已有旧 Sky 账号，需删除 `backend/data/app.db` 重建或请管理员重置密码。

## 启动后端

详见 [backend/README.md](backend/README.md)。

简要步骤：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
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

- 后端：<http://127.0.0.1:8001>
- 前端：<http://127.0.0.1:3000>

若 `npm run dev:backend` 找不到依赖，请在已激活的 `backend/.venv` 环境中手动执行 `uvicorn`（见上文）。

## CORS

默认允许 `http://127.0.0.1:3000`、`localhost:3000`、`5500`、`8080` 等。其他端口可设置环境变量：

```bash
set PM_CORS_ORIGINS=http://127.0.0.1:4173,http://localhost:4173
```

（Linux/macOS 使用 `export`。）
