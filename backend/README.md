# 后端（FastAPI）

## 环境

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

## 启动

在 `backend` 目录下（已激活 venv）：

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- 接口文档：<http://127.0.0.1:8001/docs>
- 健康检查：`GET /health`

## 环境变量（鉴权）

| 变量 | 说明 |
|------|------|
| `PM_SESSION_SECRET` | Starlette 会话密钥；生产务必自定义 |
| `PM_SKY_INITIAL_PASSWORD` | 可选。覆盖 **Sky** 的初始密码；**不设置时默认为 `123123`**（生产请修改） |
| `PM_AUTH_DISABLED` | `true` 时跳过登录校验（仅开发） |
| `PM_SESSION_SAME_SITE` | 会话 Cookie 的 SameSite（默认 `lax`） |
| `PM_SESSION_HTTPS_ONLY` | 是否仅 HTTPS 下发 Cookie（默认 `false`） |
| `PM_AUTH_MODE` | 预留：`local`（默认），未来可对接 OA |

## API 摘要

除另有说明外，`/api/v1/manpower|phase|risk` 的 **GET 需已登录**，**PUT 需管理员**。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 登录（JSON：`username`, `password`），下发会话 Cookie |
| POST | `/api/v1/auth/logout` | 退出 |
| GET | `/api/v1/auth/me` | 当前用户 `{ id, username, role }` |
| GET | `/api/v1/auth/oa/authorize` | 预留 OA，未实现时返回 501 |
| GET | `/api/v1/users` | 用户列表（**管理员**） |
| POST | `/api/v1/users` | 创建用户（**管理员**） |
| PATCH | `/api/v1/users/{id}` | 更新角色、启用状态、重置密码（**管理员**） |
| DELETE | `/api/v1/users/{id}` | 删除用户（**管理员**，不可删除最后一名活跃管理员） |
| GET | `/api/v1/manpower` | 读取人力登记 |
| PUT | `/api/v1/manpower` | 保存人力登记 |
| GET | `/api/v1/phase` | 读取阶段状态 |
| PUT | `/api/v1/phase` | 保存阶段状态 |
| GET | `/api/v1/risk` | 读取风险登记 |
| PUT | `/api/v1/risk` | 保存风险登记 |

数据存放在 `backend/data/app.db`（SQLite），含 `users` 与 `registry` 表。CORS 来源可通过 `PM_CORS_ORIGINS`（逗号分隔）覆盖，参见 `app/config.py`。
