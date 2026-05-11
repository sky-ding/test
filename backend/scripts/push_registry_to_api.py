#!/usr/bin/env python3
"""
将本地导出的 registry JSON 推送到远端 PM API（登录后调用 PUT /manpower|phase|risk）。

示例（在 backend 目录）：
  python scripts/merge_registry_dir_for_api_push.py --from-dir data/registry-import --out data/registry-bundle-for-api.json
  python scripts/push_registry_to_api.py ^
    --base https://ipd-pmo.vip.vip.com ^
    --username sky.ding ^
    --password 你的密码 ^
    --file data/registry-bundle-for-api.json

若线上 phase PUT 报 422 且含 planMatch / extra_forbidden，说明远端尚未支持该字段，请加：
  --legacy-phase

输入 JSON 须为顶层含 manpower / phase / risk 三个键的对象（见 merge_registry_dir_for_api_push.py）。
"""
from __future__ import annotations

import argparse
import copy
import json
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

ENDPOINTS = {
    "manpower": "/api/v1/manpower",
    "phase": "/api/v1/phase",
    "risk": "/api/v1/risk",
}


def _post_json(opener: urllib.request.OpenerDirector, url: str, body: dict[str, Any]) -> tuple[int, str]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=30) as resp:
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def _put_json(opener: urllib.request.OpenerDirector, url: str, body: dict[str, Any]) -> tuple[int, str]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    # 登记 JSON 较大时默认 20s 易超时
    with opener.open(req, timeout=120) as resp:
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def _load_payload(path: Path) -> dict[str, dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("JSON 顶层必须是对象")
    out: dict[str, dict[str, Any]] = {}
    for k in ("manpower", "phase", "risk"):
        v = obj.get(k)
        if isinstance(v, dict):
            out[k] = v
    if not out:
        raise ValueError("未找到 manpower/phase/risk 数据")
    return out


def strip_plan_match_from_phase(phase_body: dict[str, Any]) -> dict[str, Any]:
    """旧版线上 API 的 PhaseMonthRow 不含 planMatch（extra=forbid），去掉该字段后再 PUT。"""
    out = copy.deepcopy(phase_body)
    for prog in out.get("phaseData") or []:
        if not isinstance(prog, dict):
            continue
        for pset in prog.get("projectSets") or []:
            if not isinstance(pset, dict):
                continue
            for proj in pset.get("subProjects") or []:
                if not isinstance(proj, dict):
                    continue
                pbm = proj.get("phaseByMonth")
                if not isinstance(pbm, dict):
                    continue
                for _ym, row in list(pbm.items()):
                    if isinstance(row, dict) and "planMatch" in row:
                        del row["planMatch"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Push registry JSON to remote PM API")
    parser.add_argument("--base", required=True, help="API base, e.g. http://ipd-pmo.vip.vip.com")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument("--file", required=True, help="Path to JSON file")
    parser.add_argument(
        "--legacy-phase",
        action="store_true",
        help="推送前从 phase.phaseByMonth 各月中移除 planMatch（兼容尚未升级的后端，避免 422）",
    )
    args = parser.parse_args()

    base = args.base.rstrip("/")
    src = Path(args.file).expanduser().resolve()
    if not src.is_file():
        print(f"文件不存在：{src}")
        return 1

    try:
        payloads = _load_payload(src)
    except Exception as exc:
        print(f"读取数据失败：{exc}")
        return 1

    if args.legacy_phase and "phase" in payloads:
        payloads["phase"] = strip_plan_match_from_phase(payloads["phase"])
        print("已按 --legacy-phase 移除 phase 中的 planMatch 字段")

    for k, v in payloads.items():
        b = len(json.dumps(v, ensure_ascii=False).encode("utf-8"))
        print(f"待推送 {k}: 约 {b // 1024} KiB")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    try:
        code, login_body = _post_json(
            opener,
            f"{base}/api/v1/auth/login",
            {"username": args.username, "password": args.password},
        )
        if code != 200:
            print(f"登录失败，HTTP {code}: {login_body[:800]}")
            return 1
        print("登录: ok")
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"登录失败，HTTP {exc.code}: {err[:800]}")
        return 1
    except Exception as exc:
        print(f"登录失败：{exc}")
        return 1

    success: list[str] = []
    for key, path in ENDPOINTS.items():
        body = payloads.get(key)
        if body is None:
            continue
        try:
            code, put_body = _put_json(opener, f"{base}{path}", body)
            if code == 200:
                success.append(key)
                print(f"{key}: ok（响应约 {len(put_body)} 字符）")
            else:
                print(f"{key}: HTTP {code}: {put_body[:500]}")
                return 1
        except urllib.error.HTTPError as exc:
            err = exc.read().decode("utf-8", errors="replace")
            print(f"{key}: HTTP {exc.code}: {err[:800]}")
            return 1
        except Exception as exc:
            print(f"{key}: 请求失败 {exc}")
            return 1

    print(f"完成：{', '.join(success)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

