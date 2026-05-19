"""前端项目树联动的脚本化契约测试。

当前前端是单页 HTML，尚未拆出 JS 模块；这里用静态契约保护关键保存链路，
避免项目树落库、_subProjectId 绑定和风险提示文案再次回退。
"""

from __future__ import annotations

from pathlib import Path


FRONTEND_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


def _html() -> str:
    return FRONTEND_INDEX.read_text(encoding="utf-8")


def test_program_tree_skeleton_keeps_backend_ids() -> None:
    src = _html()

    assert "_programId: prog.id" in src
    assert "_subProgramId: spg.id" in src
    assert "_subProjectId: sid" in src


def test_manpower_sync_preserves_sub_project_id() -> None:
    src = _html()
    sync_start = src.index("function syncManpowerStructureFromPhase()")
    sync_end = src.index("function ensureProjectHasManpowerByMonth", sync_start)
    sync_body = src[sync_start:sync_end]

    assert "_subProjectId: p._subProjectId" in sync_body
    assert "_subProjectId: phP && phP._subProjectId" in sync_body
    assert "_programId: phSet._programId" in sync_body
    assert "_subProgramId: phProjectSet && phProjectSet._subProgramId" in sync_body


def test_relational_project_tree_buttons_call_backend_helpers() -> None:
    src = _html()

    for helper in (
        "createRelationalProgramWithDefaultLeaf",
        "createRelationalSubProgramWithDefaultLeaf",
        "createRelationalSubProject",
        "patchRelationalProgram",
        "patchRelationalSubProgram",
        "patchRelationalSubProject",
        "deleteRelationalProgram",
        "deleteRelationalSubProgram",
        "deleteRelationalSubProject",
    ):
        assert helper in src

    assert "await reloadRegistryAfterProjectTreeChange();" in src


def test_risk_prompt_no_longer_points_to_settings_project_tree() -> None:
    src = _html()

    assert "请先在「设置」中为该年创建项目树" not in src
    assert "请先在项目阶段状态或部门项目人力登记页创建项目树" in src
    assert "firstSubProjectMetaInTree()" in src


def test_manpower_tables_use_sticky_pin_columns() -> None:
    src = _html()

    assert "function applyManpowerTableStickyPins(" in src
    assert "appendManpowerTheadStructureCells(tr1, tr2)" in src
    assert "applyStickyPinLeftFromDom(document.getElementById('register-table'))" in src
    assert "register-table-frozen" not in src
    assert "function ensureManpowerSplitScrollSync(" not in src
    assert ":not(.pin-col-1):not(.pin-col-2):not(.pin-col-3)" in src
    assert "#panel-manpower #register-table thead .pin-col-1" in src
    assert "thead tr:nth-child(2) > th.pin-col-2" in src
    assert "table.tHead.rows[1]" in src
    assert "querySelector('colgroup')" in src
