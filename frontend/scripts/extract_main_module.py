# -*- coding: utf-8 -*-
"""Extract inline script from index.html -> js/main-app.js (ES module body)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
OUT = ROOT / "js" / "main-app.js"

HEADER = '''import { refreshPmApiBase, getPmApiBase, pmFetch } from './api/registry.js';
import {
  S,
  defaultDeptGroups,
  QUARTER_MONTH_LABELS,
  QUARTER_MONTHS,
  PHASE_FIELD_KEYS,
  PHASE_FIELD_LABELS,
  STORAGE_KEY_MANPOWER,
  STORAGE_KEY_REGISTER_COLS,
  STORAGE_KEY_RISK,
  STORAGE_KEY_PHASE,
  STORAGE_KEY_LEGACY,
  STORAGE_KEY_APP_SETTINGS
} from './state.js';

refreshPmApiBase();

'''

_STR_HOLDER = "__PM_STR_{}__"


def protect_strings(s: str) -> tuple[str, list[str]]:
    store: list[str] = []

    def repl(m: re.Match) -> str:
        store.append(m.group(0))
        return _STR_HOLDER.format(len(store) - 1)

    out = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", repl, s)
    return out, store


def restore_strings(s: str, store: list[str]) -> str:
    for i, val in enumerate(store):
        s = s.replace(_STR_HOLDER.format(i), val)
    return s


def sub_global(name: str, replacement: str, body: str) -> str:
    pat = rf"(?<![\w$.]){re.escape(name)}(?![\w$])(?!\s*:)"
    return re.sub(pat, replacement, body)


def main():
    text = INDEX.read_text(encoding="utf-8").replace("\r\n", "\n")
    chart_token = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>'
    end_marker = "\n  </script>\n  <script>\n// 定义指引数据结构"
    if chart_token not in text or end_marker not in text:
        raise SystemExit("Could not locate chart script or main/guide script boundary")
    start = text.index(chart_token) + len(chart_token)
    chunk = text[start:]
    chunk = chunk[chunk.index("<script>") + len("<script>") :]
    end = chunk.index(end_marker)
    body = chunk[:end].lstrip("\n")

    lines = body.splitlines()
    body = "\n".join(line[4:] if line.startswith("    ") else line for line in lines)

    body = re.sub(
        r"// 基础数据结构\nlet data = \[[\s\S]*?\n\];\n\n"
        r"let phaseData = \[[\s\S]*?\n\];\n\n"
        r"/\*\* 部门分组默认结构[\s\S]*?\nfunction defaultDeptGroups\(\) \{[\s\S]*?\n\}\n\n"
        r"/\*\* 部门分组[\s\S]*?\nlet deptGroups = defaultDeptGroups\(\);\n\n",
        "",
        body,
        count=1,
    )

    body = re.sub(
        r"let manpowerSubView = 'month';\n"
        r"let manpowerSelYear = new Date\(\)\.getFullYear\(\);\n"
        r"let manpowerSelMonth = new Date\(\)\.getMonth\(\) \+ 1;\n"
        r"let manpowerSelQuarter = Math\.floor\(\(manpowerSelMonth - 1\) / 3\);\n"
        r"const QUARTER_MONTH_LABELS = \[[^\]]+\];\n"
        r"const QUARTER_MONTHS = \[[\s\S]*?\];\n\n"
        r"function ymKey",
        "function ymKey",
        body,
        count=1,
    )

    body = re.sub(
        r"let phaseSelYear = new Date\(\)\.getFullYear\(\);\n"
        r"let phaseSelMonth = new Date\(\)\.getMonth\(\) \+ 1;\n"
        r"const PHASE_FIELD_KEYS = \[[^\]]+\];\n"
        r"const PHASE_FIELD_LABELS = \{[\s\S]*?\};\n\n"
        r"function getProgramProjectSets",
        "function getProgramProjectSets",
        body,
        count=1,
    )

    body = re.sub(
        r"let manpowerAnalysisCharts = \[\];\nconst MANPOWER_CHART_COLORS",
        "const MANPOWER_CHART_COLORS",
        body,
        count=1,
    )

    body = re.sub(
        r"let registerColWidths = \[\];\nlet registerColResizeDrag = null;\n\nfunction getRegisterColCount",
        "function getRegisterColCount",
        body,
        count=1,
    )

    body = re.sub(
        r"// 用于弹窗时定位删除内容\nlet delCtx = null;[^\n]*\nlet modalFocusReturn = null;\n\nfunction openDeleteModal",
        "function openDeleteModal",
        body,
        count=1,
    )

    body = re.sub(
        r"// —— 项目风险登记 ——\nlet riskRows = \[\];\n"
        r"/\*\* 当前列表排序：点击表头字段切换升序/降序 \*/\nlet riskSortState = \{ key: null, dir: 'asc' \};\n\n"
        r"const STORAGE_KEY_MANPOWER = 'PM-tool-manpower-v1';\n"
        r"const STORAGE_KEY_REGISTER_COLS = 'PM-tool-register-colwidths-v1';\n"
        r"const STORAGE_KEY_RISK = 'PM-tool-risk-v1';\n"
        r"const STORAGE_KEY_PHASE = 'PM-tool-phase-v1';\n"
        r"const STORAGE_KEY_LEGACY = 'PM-tool-data-v1';\n"
        r"const STORAGE_KEY_APP_SETTINGS = 'PM-tool-app-settings-v1';\n\n"
        r"function resolveApiBase",
        "function resolveApiBase",
        body,
        count=1,
    )

    body = re.sub(
        r"function resolveApiBase\(\) \{[\s\S]*?\nvar PM_API_BASE = resolveApiBase\(\);\n\n"
        r"function pmApiUrl\(path\) \{[\s\S]*?\n\}\n\n"
        r"function pmFetch\(path, options\) \{[\s\S]*?\n\}\n\n",
        "",
        body,
        count=1,
    )

    body = re.sub(
        r"let appUserRole = 'viewer';\nconst panelEditMode = \{ manpower: false, phase: false, risk: false \};\n\nfunction syncPmRoleGlobal",
        "function syncPmRoleGlobal",
        body,
        count=1,
    )

    body = re.sub(
        r"let riskAnalysisCharts = \[\];\nlet lastRiskAnalysisStats = null;\nlet riskAnalysisSortMode = 'count';\n\nfunction riskLevelToNum",
        "function riskLevelToNum",
        body,
        count=1,
    )

    body, str_store = protect_strings(body)

    for name in [
        "riskAnalysisSortMode",
        "lastRiskAnalysisStats",
        "riskAnalysisCharts",
        "panelEditMode",
        "appUserRole",
        "modalFocusReturn",
        "riskSortState",
        "riskRows",
        "delCtx",
        "registerColResizeDrag",
        "registerColWidths",
        "manpowerAnalysisCharts",
        "phaseSelMonth",
        "phaseSelYear",
        "manpowerSelQuarter",
        "manpowerSelMonth",
        "manpowerSelYear",
        "manpowerSubView",
        "deptGroups",
        "phaseData",
        "data",
    ]:
        body = sub_global(name, f"S.{name}", body)

    body = restore_strings(body, str_store)

    # 避免将 Chart.js 配置里的字面键 data / datasets 误替换为 S.data
    body = re.sub(r"(\n\s+)S\.data: \{", r"\1data: {", body)
    body = re.sub(r"(\n\s+)S\.datasets: \[", r"\1datasets: [", body)
    body = body.replace("S.data: setVals,", "data: setVals,")
    body = body.replace("S.data: vals,", "data: vals,")
    body = body.replace("S.data: counts,", "data: counts,")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HEADER + body + "\n", encoding="utf-8")
    print("Wrote", OUT, "length", len(HEADER + body))


if __name__ == "__main__":
    main()
