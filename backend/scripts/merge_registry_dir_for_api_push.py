#!/usr/bin/env python3
"""
将 import_excel_registry / import_registry_data 使用的三份 JSON 合并为
push_registry_to_api.py 所需的单文件格式：

  { "manpower": {...}, "phase": {...}, "risk": {...} }

用法（在 backend 目录）：
  python scripts/merge_registry_dir_for_api_push.py
  python scripts/merge_registry_dir_for_api_push.py --from-dir data/registry-import --out data/registry-bundle-for-api.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--from-dir",
        type=Path,
        default=Path("data/registry-import"),
        help="含 phase.json / manpower.json / risk.json 的目录",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("data/registry-bundle-for-api.json"),
        help="输出路径（供 push_registry_to_api.py --file 使用）",
    )
    args = ap.parse_args()
    d = args.from_dir.expanduser().resolve()
    if not d.is_dir():
        print(f"目录不存在：{d}", file=sys.stderr)
        return 1
    paths = {k: d / f"{k}.json" for k in ("phase", "manpower", "risk")}
    for k, p in paths.items():
        if not p.is_file():
            print(f"缺少文件：{p}", file=sys.stderr)
            return 1
    bundle = {
        "phase": json.loads(paths["phase"].read_text(encoding="utf-8")),
        "manpower": json.loads(paths["manpower"].read_text(encoding="utf-8")),
        "risk": json.loads(paths["risk"].read_text(encoding="utf-8")),
    }
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
