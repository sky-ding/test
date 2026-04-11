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
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：`GET /health`

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/manpower` | 读取人力登记（默认空 `data`/`deptGroups`） |
| PUT | `/api/v1/manpower` | 保存人力登记 |
| GET | `/api/v1/phase` | 读取阶段状态 |
| PUT | `/api/v1/phase` | 保存阶段状态 |
| GET | `/api/v1/risk` | 读取风险登记 |
| PUT | `/api/v1/risk` | 保存风险登记 |

数据存放在 `backend/data/app.db`（SQLite）。CORS 来源可通过环境变量 `PM_CORS_ORIGINS`（逗号分隔）覆盖，参见 `app/config.py`。
