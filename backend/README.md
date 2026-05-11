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
4. 连接与表行数冒烟：

```bash
python scripts/check_db.py
```

5. **从现有 SQLite 迁移**（本机已有 `data/app.db` 且已配置 `PM_MYSQL_*`）：

```bash
python scripts/migrate_sqlite_to_mysql.py
```

目标 MySQL 里若已有 `users`/`registry` 数据，脚本默认会拒绝覆盖；需使用 `--force`（**会清空** MySQL 侧这两张表后再导入）。

6. **迁移后验证（建议每台实例或每次发版执行）**：`python scripts/check_db.py`；再用管理员账号调 `GET/PUT /api/v1/manpower`、`phase`、`risk`（见 `/docs`）。

未配置 `PM_MYSQL_*` 时仍回落 **本地 SQLite** `backend/data/app.db`，便于单人本机开发。

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

## 历史 Excel 一次导入数据库（手把手）

整体做两件事：**先把 Excel 转成三份 JSON**，**再把 JSON 写进数据库**（`registry` 表里的 `manpower` / `phase` / `risk` 三行）。  
数据库是 **MySQL 还是本机 SQLite**，只取决于 `backend/.env` 里有没有配齐 `PM_MYSQL_HOST` + `PM_MYSQL_USER` + `PM_MYSQL_DATABASE`：配齐了走 MySQL，没配齐走 `backend/data/app.db`。

### 0. 一次性准备

1. 安装依赖：在 `backend` 目录建好 venv、`pip install -r requirements.txt`（见上文「环境」）。  
2. 把 `backend/.env.example` 复制为 **`backend/.env`**。  
   - 要写入 **MySQL**：在 `.env` 里填好 `PM_MYSQL_*` 和 `PM_SESSION_SECRET`，并先在 MySQL 里建好空库。  
   - 只在**本机试跑**：可以不配 MySQL，数据会进 **`backend/data/app.db`**。  
3. Excel 文件路径改成你自己的，例如：`D:\Users\你的用户名\Desktop\项目管理状态月度评估2026.xlsx`。

### 1. 用 Excel 生成三份 JSON（在「仓库根目录」执行）

仓库根目录是指包含 `frontend`、`backend`、`scripts` 的那一层（例如 `d:\Study\test01\test`），**不要**先 `cd backend`。

在 PowerShell 里（已激活 backend 的 venv，这样才有 `openpyxl` 等依赖）：

```powershell
cd d:\Study\test01\test
python scripts/import_excel_registry.py `
  --excel "D:\Users\sky.ding\Desktop\项目管理状态月度评估2026.xlsx" `
  --year 2026 `
  --out-dir backend/data/registry-import
```

成功后会多出目录 **`backend/data/registry-import/`**，里面有：

- `phase.json`（阶段）
- `manpower.json`（人力）
- `risk.json`（风险）

终端里若出现 `Pydantic 校验通过` 和 `已写入: ...`，说明这一步没问题。

### 2. 把三份 JSON 写入数据库（在「backend」目录执行）

```powershell
cd d:\Study\test01\test\backend

# 建议先 dry-run：只校验、不写库
python scripts/import_registry_data.py --from-registry-dir data/registry-import --dry-run

# 确认无误后再真正写入（会覆盖库里已有的三条 registry）
python scripts/import_registry_data.py --from-registry-dir data/registry-import --force
```

含义简要说明：

- **`--from-registry-dir data/registry-import`**：从该相对路径读上面三份 JSON，一次导入三个模块。  
- **`--dry-run`**：校验数据格式，**不写数据库**。  
- **`--force`**：**一定要加**才会覆盖库里已有的 `manpower` / `phase` / `risk`；不加的话若已有数据会跳过。

导入完成后，用管理员登录前端或调 `GET /api/v1/phase` 等即可看到数据。

### 3. 在 **ipd-pmo.vip.vip.com** 网页上看到同一份数据（不经本机 MySQL）

线上站点读的是**部署环境自己的 MySQL**；你在本机 `.env` 里导入的数据不会自动出现在线上。需要把 JSON **通过 HTTP API 推上去**（需 **管理员** 账号；**会覆盖**线上当前 `manpower` / `phase` / `risk` 三块登记数据）。

在 `backend` 目录、已激活 venv：

```powershell
# 1) 合并 registry-import 下三份 JSON 为 push 脚本所需的一个文件
python scripts/merge_registry_dir_for_api_push.py --from-dir data/registry-import --out data/registry-bundle-for-api.json

# 2) 登录并 PUT（密码填真实值，勿写「你的密码」四字；--base 与浏览器一致）
python scripts/push_registry_to_api.py --base http://ipd-pmo.vip.vip.com --username sky.ding --password 真实密码 --file data/registry-bundle-for-api.json

# 若 phase 返回 422 且提示 planMatch / extra_forbidden（线上后端较旧），再加：
# python scripts/push_registry_to_api.py ... --legacy-phase

# （可选）推送前先看线上当前有没有数据：应看到 phase 顶层条目数>0 等
python scripts/verify_remote_registry.py --base http://ipd-pmo.vip.vip.com --username sky.ding --password 你的密码
```

说明：

- 若公司只开放 **http**，把 `--base` 改成 `http://ipd-pmo.vip.vip.com`。  
- 须在**能访问该域名**的网络（如公司 VPN）下执行。  
- 成功时终端会打印 `登录: ok`、`manpower: ok`、`phase: ok`、`risk: ok`；再在浏览器强刷页面即可。  
- 若网页仍为空，多半是**尚未成功执行 push** 或 **--base 与浏览器协议不一致**；请先跑 `verify_remote_registry.py`，若 `phase: 顶层条目数=0` 再执行 merge + push。

---

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
