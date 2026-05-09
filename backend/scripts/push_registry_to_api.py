#!/usr/bin/env python3
"""
将本地导出的 registry JSON 推送到远端 PM API（登录后调用 PUT /manpower|phase|risk）。

示例（在 backend 目录）：
  python scripts/push_registry_to_api.py ^
    --base http://ipd-pmo.vip.vip.com ^
    --username Sky ^
    --password 123123 ^
    --file data/import-for-remote.json
"""
from __future__ import annotations

import argparse
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
    with opener.open(req, timeout=15) as resp:
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def _put_json(opener: urllib.request.OpenerDirector, url: str, body: dict[str, Any]) -> tuple[int, str]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with opener.open(req, timeout=20) as resp:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Push registry JSON to remote PM API")
    parser.add_argument("--base", required=True, help="API base, e.g. http://ipd-pmo.vip.vip.com")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument("--file", required=True, help="Path to JSON file")
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

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    try:
        code, _ = _post_json(
            opener,
            f"{base}/api/v1/auth/login",
            {"username": args.username, "password": args.password},
        )
        if code != 200:
            print(f"登录失败，HTTP {code}")
            return 1
    except urllib.error.HTTPError as exc:
        print(f"登录失败，HTTP {exc.code}")
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
            code, _ = _put_json(opener, f"{base}{path}", body)
            if code == 200:
                success.append(key)
                print(f"{key}: ok")
            else:
                print(f"{key}: HTTP {code}")
                return 1
        except urllib.error.HTTPError as exc:
            print(f"{key}: HTTP {exc.code}")
            return 1
        except Exception as exc:
            print(f"{key}: 请求失败 {exc}")
            return 1

    print(f"完成：{', '.join(success)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

