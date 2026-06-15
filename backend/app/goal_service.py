"""目标进展自动推导服务。"""

from __future__ import annotations

from datetime import date
from sqlalchemy.orm import Session

from app.models_relational import Goal, GoalLink, Milestone, Task


def _period_for_date(d: date) -> str:
    """将日期转为 YYYY-MM 格式。"""
    return f"{d.year:04d}-{d.month:02d}"


def _quarter_for_date(d: date) -> str:
    """将日期转为 YYYY-Q1/Q2/Q3/Q4 格式。"""
    q = (d.month - 1) // 3 + 1
    return f"{d.year:04d}-Q{q}"


def _collect_linked_items(db: Session, goal: Goal) -> tuple[list[Milestone], list[Task]]:
    """获取一个目标关联的所有里程碑和任务。"""
    milestones: list[Milestone] = []
    tasks: list[Task] = []
    for link in goal.links:
        if link.target_type == "milestone":
            m = db.get(Milestone, link.target_id)
            if m and m.sub_project_id == goal.sub_project_id:
                milestones.append(m)
        elif link.target_type == "task":
            t = db.get(Task, link.target_id)
            if t and t.sub_project_id == goal.sub_project_id:
                tasks.append(t)
    return milestones, tasks


def derive_goal_progress(
    db: Session,
    goal: Goal,
    *,
    year: int,
) -> list[dict]:
    """
    为一个目标推导年度内各季度和各月的进展。

    返回格式:
    [
        {
            "period": "2026-Q2",
            "related_items": ["完成架构设计"],
            "progress_pct": 100.0,
            "status": "completed"
        },
        ...
    ]
    """
    milestones, tasks = _collect_linked_items(db, goal)

    if not milestones and not tasks:
        # 无关联 → 无推导数据，返回空列表
        return []

    # 按季度聚合
    quarter_items: dict[str, list[dict]] = {}
    month_items: dict[str, list[dict]] = {}

    for m in milestones:
        q = _quarter_for_date(m.planned_date)
        mo = _period_for_date(m.planned_date)
        item = {
            "name": m.name,
            "type": "milestone",
            "status": m.status,  # 'pending' / 'in-progress' / 'completed' / 'overdue'
            "date": m.planned_date,
        }
        quarter_items.setdefault(q, []).append(item)
        month_items.setdefault(mo, []).append(item)

    for t in tasks:
        # 任务按 start_date 所在的时间窗口聚合
        q = _quarter_for_date(t.start_date)
        mo = _period_for_date(t.start_date)
        item = {
            "name": t.name,
            "type": "task",
            "progress": t.progress,  # 0-100
            "start_date": t.start_date,
            "end_date": t.end_date,
        }
        quarter_items.setdefault(q, []).append(item)
        month_items.setdefault(mo, []).append(item)

    results: list[dict] = []

    # 计算每个时间窗口的聚合状态
    for period, items in sorted(quarter_items.items()):
        results.append(_aggregate_period(period, items))
    for period, items in sorted(month_items.items()):
        results.append(_aggregate_period(period, items))

    return results


def _aggregate_period(period: str, items: list[dict]) -> dict:
    """聚合一个时间窗口内的里程碑/任务状态。

    里程碑和任务统一计算进度：
    - 里程碑: completed=100%, in-progress=50%, not-started=0%
    - 任务: 直接使用 progress 字段
    - 混合时取所有项的平均进度
    """
    related_names = [i["name"] for i in items]

    # 统一计算进度
    progress_values: list[float] = []
    for item in items:
        if item["type"] == "milestone":
            # 里程碑状态转进度
            status = item.get("status", "not-started")
            if status == "completed":
                progress_values.append(100.0)
            elif status == "in-progress":
                progress_values.append(50.0)
            else:  # not-started or other
                progress_values.append(0.0)
        elif item["type"] == "task":
            # 任务直接使用 progress 字段
            progress_values.append(float(item.get("progress", 0)))

    if progress_values:
        progress_pct = round(sum(progress_values) / len(progress_values), 1)
    else:
        progress_pct = None

    # 判断状态
    if progress_pct is not None and progress_pct >= 100:
        status = "completed"
    elif progress_pct is not None and progress_pct > 0:
        status = "in_progress"
    else:
        status = "not_started"

    return {
        "period": period,
        "related_items": related_names,
        "progress_pct": progress_pct,
        "status": status,
    }


def compute_goal_overall_status(goal: Goal, derived: list[dict], year: int | None = None) -> str:
    """
    计算目标的整体状态。

    返回: 'completed' | 'on_track' | 'at_risk' | 'behind' | 'not_started'
    """
    if goal.direction == "boolean":
        # 二值型:看关联项的完成情况
        monthly = [d for d in derived if "Q" not in d["period"]]
        if not monthly:
            return "not_started"

        completed_count = sum(1 for d in monthly if d["status"] == "completed")
        total = len(monthly)

        if completed_count == total:
            return "completed"       # 全部完成
        elif completed_count > 0:
            return "on_track"        # 部分完成
        elif any(d["status"] == "in_progress" for d in monthly):
            return "on_track"        # 有进行中的
        else:
            return "not_started"     # 都未开始

    if not derived:
        # 无推导数据 → 用 current_value 和 initial_target 比较
        if goal.current_value:
            return "on_track"  # 有手动值就认为在跟踪中
        return "not_started"

    # 有推导数据:看年度整体进度
    y = year or date.today().year
    year_prefix = f"{y:04d}"
    year_items = [d for d in derived if d["period"].startswith(year_prefix) and "Q" not in d["period"]]
    if not year_items:
        return "not_started"

    total_progress = sum(d["progress_pct"] or 0 for d in year_items)
    avg = total_progress / len(year_items)

    # 判断是否 at_risk:当前月份过半但进度不足 50%
    now = date.today()
    current_month = f"{now.year:04d}-{now.month:02d}"
    current_items = [d for d in derived if d["period"] == current_month]
    if current_items:
        cp = current_items[0]["progress_pct"] or 0
        if cp < 50 and now.day > 15:
            return "at_risk"

    if avg >= 80:
        return "on_track"
    elif avg >= 50:
        return "at_risk"
    else:
        return "behind"


def build_goal_summary(
    db: Session,
    sub_project_id: int,
    year: int,
) -> list[dict]:
    """
    为项目阶段状态页构建目标摘要(只读)。

    返回格式供前端渲染用。
    """
    from app.models_relational import Goal as GoalModel, SubProject
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # 预加载 links 避免 N+1
    goals = list(
        db.scalars(
            select(GoalModel)
            .where(GoalModel.sub_project_id == sub_project_id)
            .options(selectinload(GoalModel.links))
            .order_by(GoalModel.sort_order, GoalModel.id)
        ).all()
    )

    # 获取子项目名称
    sp = db.get(SubProject, sub_project_id)
    sp_name = sp.name if sp else ""

    summaries: list[dict] = []
    for goal in goals:
        # 优先取期中调整值
        target = goal.mid_term_target or goal.initial_target

        # 获取当前值
        if goal.links:
            # 有关联 → 自动推导当前月进度
            derived = derive_goal_progress(db, goal, year=year)
            now = date.today()
            current_month = f"{now.year:04d}-{now.month:02d}"
            current = next((d for d in derived if d["period"] == current_month), None)
            if current and current["progress_pct"] is not None:
                current_value = f"{current['progress_pct']}%"
            elif goal.current_value:
                current_value = goal.current_value
            else:
                current_value = "-"
            status = compute_goal_overall_status(goal, derived, year=year)
        else:
            # 无关联 → 取手动更新的最新值
            current_value = goal.current_value or "-"
            status = "on_track" if goal.current_value else "not_started"

        emoji_map = {
            "completed": "✅",
            "on_track": "🟢",
            "at_risk": "🟡",
            "behind": "🔴",
            "not_started": "⏳",
        }

        summaries.append({
            "sub_project_id": sub_project_id,
            "sub_project_name": sp_name,
            "name": goal.name,
            "metric_unit": goal.metric_unit,
            "target_value": target,
            "current_value": current_value,
            "status": status,
            "status_emoji": emoji_map.get(status, "⏳"),
        })

    return summaries
