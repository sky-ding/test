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

## MySQL（可选）

同时设置以下变量时，应用使用 **MySQL**；否则仍使用 `backend/data/app.db`（SQLite）。

| 变量 | 说明 |
|------|------|
| `PM_MYSQL_HOST` | 主机，如 `127.0.0.1` |
| `PM_MYSQL_PORT` | 端口，默认 `3306` |
| `PM_MYSQL_USER` | 用户名 |
| `PM_MYSQL_PASSWORD` | 密码（可含特殊字符，已做 URL 编码） |
| `PM_MYSQL_DATABASE` | 库名（须已创建，字符集建议 `utf8mb4`） |
| `PM_MYSQL_CHARSET` | 默认 `utf8mb4` |

从现有 SQLite 迁到 MySQL（在 `backend` 目录、已配置上述变量）：

```bash
python scripts/migrate_sqlite_to_mysql.py
```

若目标库已有数据（例如先启动过应用并 seed 了 Sky），需加 `--force` 清空 `users` 与 `registry` 后再导入。

## 导入已有业务数据（一次性）

当你已有历史数据（例如从浏览器 localStorage 导出的 JSON）时，可手动导入到 `registry` 表。

在 `backend` 目录执行：

```bash
# 先校验，不写库
python scripts/import_registry_data.py --file path/to/data.json --dry-run

# 导入全部识别到的模块（manpower / phase / risk）
python scripts/import_registry_data.py --file path/to/data.json --force

# 仅导入单模块
python scripts/import_registry_data.py --file path/to/data.json --module manpower --force

# Excel（.xlsx）先转换并校验（不写库）
python scripts/import_registry_data.py --file path/to/data.xlsx --dry-run --export-json data/import-preview.json
```

说明：
- 本脚本仅在你手动执行时生效，不会在服务启动时自动运行。
- 支持 JSON 和 Excel（`.xlsx`）。
- JSON 支持两类顶层键：`manpower|phase|risk` 或 `PM-tool-manpower-v1|PM-tool-phase-v1|PM-tool-risk-v1`。
- Excel 约定：工作表名包含“月度执行评估（X月）/人力评估（X月）/风险监控”。
- 若库中已有对应键，默认跳过；加 `--force` 才覆盖。

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

数据：`users` 与 `registry` 表。未配置 MySQL 时为 `backend/data/app.db`（SQLite）；配置 `PM_MYSQL_*` 时使用 MySQL。CORS 来源可通过 `PM_CORS_ORIGINS`（逗号分隔）覆盖，参见 `app/config.py`。
