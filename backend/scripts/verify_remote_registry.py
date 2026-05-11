#!/usr/bin/env python3
"""
登录远端 PM API 后 GET manpower/phase/risk，打印列表长度（用于确认线上是否已有登记数据）。

用法（在 backend 目录）：
  python scripts/verify_remote_registry.py --base http://ipd-pmo.vip.vip.com --username sky.ding --password 你的密码
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Any


def _post_json(opener: urllib.request.OpenerDirector, url: str, body: dict[str, Any]) -> tuple[int, str]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=20) as resp:
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def _get_json(opener: urllib.request.OpenerDirector, url: str) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(url, method="GET")
    with opener.open(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return int(resp.status), json.loads(raw)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True, help="与浏览器一致，如 http://ipd-pmo.vip.vip.com")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()
    base = args.base.rstrip("/")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    try:
        code, text = _post_json(
            opener,
            f"{base}/api/v1/auth/login",
            {"username": args.username, "password": args.password},
        )
        if code != 200:
            print(f"登录失败 HTTP {code}: {text[:500]}", file=sys.stderr)
            return 1
        print("登录: ok")
    except urllib.error.HTTPError as e:
        print(f"登录失败 HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:800]}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"登录失败: {e}", file=sys.stderr)
        return 1

    for name, path in (
        ("phase", "/api/v1/phase"),
        ("manpower", "/api/v1/manpower"),
        ("risk", "/api/v1/risk"),
    ):
        try:
            code, obj = _get_json(opener, f"{base}{path}")
        except urllib.error.HTTPError as e:
            print(f"{name}: HTTP {e.code}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"{name}: {e}", file=sys.stderr)
            return 1
        if code != 200:
            print(f"{name}: HTTP {code}", file=sys.stderr)
            return 1
        if name == "phase":
            n = len(obj.get("phaseData") or [])
        elif name == "manpower":
            n = len(obj.get("data") or [])
        else:
            n = len(obj.get("riskRows") or [])
        raw_len = len(json.dumps(obj, ensure_ascii=False))
        print(f"{name}: 顶层条目数={n}, JSON 约 {raw_len} 字符")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
