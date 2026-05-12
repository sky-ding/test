#!/usr/bin/env python3
"""
可选：将旧 registry 表中的 manpower / phase / risk JSON 迁入规范化表。

默认不执行任何写入，仅打印说明。2027 冷启动无需运行本脚本。

若确有历史迁移需求，请在此脚本中实现读 RegistryEntry、展开树与行写库逻辑，
并在测试库人工校验部门×角色枚举与 UNIQUE 约束后再在生产执行。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    p = argparse.ArgumentParser(description="Optional registry JSON → relational tables (stub).")
    p.parse_args()
    print("registry_json_to_sql: 未实现具体迁移逻辑；需要时请扩展本脚本。")
    print("DDL 参考: backend/migrations/001_relational_schema.sql")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
