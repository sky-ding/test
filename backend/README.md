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

## 团队 / 生产：推荐 MySQL（多实例共享数据）

多机或多 Pod 跑同一套 API 时，应共用 **同一 MySQL 库**，勿各带一份 `app.db`（SQLite）。

1. 在 MySQL 中**预先创建**数据库（字符集建议 **utf8mb4**），并授予应用账号建表/读写权限。  
2. 复制 **[.env.example](.env.example)** 为 `backend/.env`，填写 **`PM_MYSQL_HOST` / `PM_MYSQL_USER` / `PM_MYSQL_DATABASE`**（及密码、端口等）；**所有实例**使用**相同**的 `PM_MYSQL_*` 与 **`PM_SESSION_SECRET`**（否则 Cookie 会话在实例间无效）。  
3. 启动应用会自动 `create_all` 建表；首次启动会 seed 内置用户（若库中尚无同名账号）。  
4. 连接与登记数据冒烟：

```bash
python scripts/check_db.py
```

5. **从现有 SQLite 迁移**（本机已有 `data/app.db` 且已配置 `PM_MYSQL_*`）：

```bash
python scripts/migrate_sqlite_to_mysql.py
```

目标 MySQL 里若已有 `users`/`registry` 数据，脚本默认会拒绝覆盖；需使用 `--force`（**会清空** MySQL 侧这两张表后再导入）。

6. **迁移后验证**：`python scripts/check_db.py`；再用管理员账号在 `/docs` 中对 `GET/PUT /api/v1/manpower`、`phase`、`risk` 做一次冒烟。

未配置 `PM_MYSQL_*` 时仍回落 **本地 SQLite** `backend/data/app.db`，便于单人本机开发。

### 故障排查：登记与页面

- **人力 / 阶段 / 风险** 由**管理员在前端**编辑并保存，经 `PUT /api/v1/manpower|phase|risk` 写入 `registry` 表（固定三个 key：`manpower`、`phase`、`risk`）。本仓库**不再提供** Excel 或批量文件导入脚本。  
- 多实例部署时，各实例的 **`PM_MYSQL_*` 与 `PM_SESSION_SECRET` 必须一致**，且指向同一库。  
- 页面表格为空：在**与线上一致**的 `backend/.env` 下执行 `python scripts/check_db.py`，查看 `len(data)` / `len(phaseData)` / `len(riskRows)` 是否为 0；若 DBA 查库有数据而页面无，核对 API 进程实际使用的连接（`host` / `port` / `database`）是否与 DBA 会话一致。  
- 人力表某年月全为 0：多为当前所选 **yyyy-MM** 在已保存的 `manpowerByMonth` 中不存在；前端会尽量对齐到数据中已有的月份。

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

## 启动时内置用户（仅当库中尚无同名账号时创建）

初始密码与 **`Sky` 相同**：优先环境变量 `PM_SKY_INITIAL_PASSWORD`，**未设置时默认为 `123123`**。

| 用户名 | 角色 |
|--------|------|
| `alfred.wang` | 管理员 |
| `fanny.wu` | 管理员 |
| `veking.lee` | 管理员 |
| `sky.ding` | 管理员 |
| `test` | 普通用户 |

另：若不存在用户名为 `sky`（不区分大小写）的账号，仍会创建兼容用的管理员 **`Sky`**。生产环境请尽快修改各账号密码。

## MySQL 环境变量说明

同时设置 **`PM_MYSQL_HOST` + `PM_MYSQL_USER` + `PM_MYSQL_DATABASE`**（均非空）时，应用使用 **MySQL**；否则使用 `backend/data/app.db`（SQLite）。

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

## MySQL 定期备份到本机

使用 **`scripts/backup_mysql_to_local.py`**：调用 **`mysqldump`** 导出当前 `.env` 中 **`PM_MYSQL_DATABASE`** 指向的整库，默认 gzip 后写入 **`backend/data/mysql-backups/`**（该目录已加入 `.gitignore`，勿提交）。

### 前置条件

1. 本机已安装 **MySQL 客户端**，且 **`mysqldump` 在 PATH 里**（PowerShell 执行 `mysqldump --version` 能成功）。  
2. 执行时工作目录为 **`backend`**，且能连通数据库（如已连 **VPN**）。  
3. 备份账号需有 **`SELECT`** 及 **`mysqldump` 所需权限**（一般只读备份账号即可）。

### 手动执行

```powershell
cd D:\Study\test01\test\backend
.\.venv\Scripts\python.exe scripts\backup_mysql_to_local.py --dry-run
.\.venv\Scripts\python.exe scripts\backup_mysql_to_local.py
.\.venv\Scripts\python.exe scripts\backup_mysql_to_local.py --out-dir D:\backup\ipd-pmo --keep-days 30
```

- **`--keep-days N`**：删除超过 N 天的旧备份（按文件名时间戳判断）。  
- **`--no-gzip`**：保留 `.sql` 不压缩。  
- **`--env-file D:\secrets\pm-prod.env`**：先从该文件加载 `PM_*`，再读配置（便于本机 `backend/.env` 仍指向开发库时，单独用一份文件备份 **ipd-pmo** 生产库）。

### Windows 任务计划程序（每天跑一次）

1. 打开「任务计划程序」→「创建任务」。  
2. **常规**：名称如 `PM MySQL 备份 ipd-pmo`；可勾选「不管用户是否登录都要运行」并设置运行账户。  
3. **触发器**：例如每天 02:00。  
4. **操作** → 新建：  
   - **程序或脚本**：`powershell.exe`  
   - **添加参数**：`-NoProfile -ExecutionPolicy Bypass -File "D:\Study\test01\test\backend\scripts\backup_mysql_to_local.ps1"`  
   - **起始于**：`D:\Study\test01\test\backend`  
5. 若备份 **生产库** 而本机 `backend\.env` 不是生产连接，请改 **`backup_mysql_to_local.ps1`** 最后一行，在 `@args` 前加入参数，例如：  
   `'scripts\backup_mysql_to_local.py', '--env-file', 'D:\secrets\pm-prod.env', '--keep-days', '14'`  
   （或把生产 `PM_*` 单独放在该 env 文件中。）

**安全说明**：备份含业务数据，请保存在加密磁盘并遵守公司数据管理规定；临时凭据文件含密码，勿入 Git。

---

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
